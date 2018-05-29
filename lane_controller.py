#!/usr/bin/env python

from CRC16Kermit import CRC16Kermit
import serial
import time
import MySQLdb

def padded_hex(i, l):
    given_int = i
    given_len = l
    # remove '0x' prefix
    hex_result = hex(given_int)[2:] 
    num_hex_chars = len(hex_result)
    extra_zeros = '0' * (given_len - num_hex_chars)

    return ('0x' + hex_result if num_hex_chars == given_len else
            '?' * given_len if num_hex_chars > given_len else
            '0x' + extra_zeros + hex_result if num_hex_chars < given_len else
            None)

def send_ack(ssn):
    #Generate Restart Confirmation <STX><SSN>A000<crc><ETX>
    #Applying nMod8+1 to SSN per mGate ICD
    if int(ssn) == -1:
        print ("Sending Restart Confirmation...")
        my_packet = "0A000"
    else:
        print ("Sending Acknowledge for message " + str((int(ssn)%8)+1) + "...")
        my_packet = str((int(ssn)%8)+1) + "A000"

    print(my_packet)
    #Calculate CRC
    x = str(padded_hex(CRC16Kermit().calculate(my_packet),4)).upper()
    x = x[2:]
    calc_crc = x[2:] + x[:2]
    my_packet = my_packet + calc_crc
    b_array = bytearray()
    b_array.extend(my_packet)
    #Send Bytes out over serial port
    ser.write(b'\x02') #STX
    ser.write(b_array)
    ser.write(b'\x03') #ETX

def write_tag_data_to_db(tag):
    try:
        query = "INSERT INTO TAG (TAG_READ_TS, TAG_DATA) VALUES(NOW(),%s);"
        curs.execute(query, [tag])
        db.commit()
    except:
        print("Error writing tag = " + tag + " to Database")
        
my_state = "AWAKE" #Default startup state of the state machine
link_state = 0 #0 => Disconnected; 1 => Connected
ssn = "" #Sequence Number Field
byte_array = "" #Array filled with received bytes
control = "" #Control Field
pl_count = 0 #Counter for Count (Packet Length) Field
count_field = "" #Count (Packet Length) Field
init_count = 0 #Counter for Initialize Message bytes
init_msg = "" #Initialize Message
crc_count = 0 #Counter for Terminator (CRC)
crc_array = "" #Array filled with CRC bytes
transp_msg_count = 0 #Counter for Transponder Message bytes
transp_msg = "" #Transponder Message
main_ssn = 0 #Send Sequence Number
main_rsn = 0 #Receive Sequence Number


#Open Database Connection
db = MySQLdb.connect("localhost", "mgate", "password", "meb")
curs=db.cursor()
#Open Serial Port
ser = serial.Serial(port='/dev/ttyAMA0', baudrate=57600, timeout=None)

while ser.isOpen():
    rx_byte = ser.read(1)
    if rx_byte != '':
        ## Looking for a Restart Request <STX>0R035<Init Msg><crc><ETX>
        if rx_byte == b'\x02' and my_state == "AWAKE":
            #LC link is disconnected
            link_state = 0
            ssn = ""
            byte_array = ""
            control = ""
            pl_count = 0
            count_field = ""
            init_count = 0
            init_msg = ""
            crc_count = 0
            crc_array = ""
            transp_msg_count = 0
            transp_msg = ""
            main_ssn = 0
            main_rsn = 0
            my_state = "SSN"
        elif my_state == "SSN":
            ssn = rx_byte.decode("utf-8")
            byte_array = ssn
            my_state = "CONTROL"                
        elif my_state == "CONTROL":
            control = rx_byte.decode("utf-8")
            byte_array = byte_array + control
            my_state = "COUNT"
        elif my_state == "COUNT":
            pl_count = pl_count + 1
            count_field = count_field + rx_byte.decode("utf-8")
            byte_array = byte_array + rx_byte.decode("utf-8")
            #Count field has a length of 3 bytes
            if pl_count == 3:
                if link_state == 0:
                    #Restart Request must have a SSN of '0', a count field of '035', and a control field 'R'
                    if ssn == '0' and count_field == "035" and control == "R":
                        my_state = "INIT_MSG"
                    #Invalid message - go back to "AWAKE" state and wait for reader to send Restart Request
                    else:
                        print("Invalid Message received from mGate Reader...")
                        print("SSN: " + str(ssn) + " Control: " + str(control) + " Count: " + str(count_field))
                        my_state = "AWAKE"
			link_state = 0
                else:
                    #Transponder Message must have a count field of '113' and a control field 'D'
                    if count_field == "113" and control == "D":
                        my_state = "TRANSPONDER_MSG"
                    #Invalid message - go back to "AWAKE" state and wait for reader to send Restart Request
                    else:
                        print("Invalid Message received from mGate Reader...")
                        print("SSN: " + str(ssn) + " Control: " + str(control) + " Count: " + str(count_field))
                        my_state = "AWAKE"
			link_state = 0
        elif my_state == "INIT_MSG":
            init_count = init_count + 1
            init_msg = init_msg + rx_byte.decode("utf-8")
            byte_array = byte_array + rx_byte.decode("utf-8")
            #Initialize message has a length of 35 bytes
            if init_count == 35:
                my_state = "CRC"
        elif my_state == "TRANSPONDER_MSG":
            transp_msg_count = transp_msg_count + 1
            transp_msg = transp_msg + rx_byte.decode("utf-8")
            byte_array = byte_array + rx_byte.decode("utf-8")
            #Transponder message has a length of 113 bytes
            if transp_msg_count == 113:
                my_state = "CRC"
        elif my_state == "CRC":
            crc_count = crc_count + 1
            crc_array = crc_array + rx_byte.decode("utf-8")
            #Terminator field is a 16 bit CCITT CRC (Kermit) and has length of 4 bytes
            if crc_count == 4:
                if link_state == 0:
                    my_state = "WAIT_ETX_RR"
                else:
                    #Transponder Message must have a count field of '113' and a control field 'D'
                    if count_field == "113" and control == "D":
                        my_state = "WAIT_ETX_TM"
        elif my_state == "WAIT_ETX_RR":
            if rx_byte == b'\x03':
                #Got ETX so let's calculate CRC and compare it to terminator field
                x = str(padded_hex(CRC16Kermit().calculate(str(byte_array)),4)).upper()
                x = x[2:]
                calc_crc = x[2:] + x[:2]
                if calc_crc == crc_array:
                    print ("Received Restart Request...")
                    print(byte_array)
                    #Acknowledge Restart Request with a Restart Confirmation
                    send_ack(-1)
                    print("Link Established!")
                    link_state = 1
                    my_state = "AWAITING_TAG_MESSAGE"
                    main_rsn = 0
        elif my_state == "WAIT_ETX_TM":
            if rx_byte == b'\x03':
                #Got ETX so let's calculate CRC and compare it to terminator field
                x = str(padded_hex(CRC16Kermit().calculate(str(byte_array)),4)).upper()
                x = x[2:]
                calc_crc = x[2:] + x[:2]
                if calc_crc == crc_array:
                    print ("Received Transponder Message...")
                    print(byte_array)
                    #Acknowledge Transponder Message
                    send_ack(main_rsn)
                    #Write transponder data into Database
                    write_tag_data_to_db(transp_msg)
                    my_state = "AWAITING_TAG_MESSAGE"
                    main_rsn = main_rsn + 1
        elif rx_byte == b'\x02' and my_state == "AWAITING_TAG_MESSAGE":
            ssn = ""
            byte_array = ""
            control = ""
            pl_count = 0
            count_field = ""
            init_count = 0
            init_msg = ""
            crc_count = 0
            crc_array = ""
            transp_msg_count = 0
            transp_msg = ""
            my_state = "SSN"
        else:
            print("Random unexpected data received on serial port, STATE: " + my_state)
            print(rx_byte)

ser.close()
db.close()
