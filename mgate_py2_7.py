import time
import serial
import random
from PyCRC.CRC16Kermit import CRC16Kermit

ser = serial.Serial(port='COM4', baudrate=57600, timeout=None)

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


def send_restart_request():
    #Generate Restart Request <STX>0R035<Init Msg><crc><ETX>
    my_packet = "0R035IN1RS " + time.strftime("%m%d%Y %H%M%S") + " MGATE SIMULTR"
    print ("Sending Restart Request...")
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

fake_tag_data_array = ["TA1RR0000F8C1143C4EF612000000000000146975785521234BABC0010200000067E8EF7F00146975785521234BABC0010200000067E8EF7F",
                       "TA1RR0000F8C1143C4EF612000000000000146975785521234BABC0010000000067E8643F00146975785521234BABC0010000000067E8643F",
                       "TA1RR0000E0C12A08F65C1200000000000654238D88A8A3A11C6C4EE700000000204C8BE30654238D88A8A3A11C6C4EE700000000204C8BE3",
                       "TA1RR0000E0C11E4A5A9C1200010000000038E4176C7C91C720BB783C00000000BD31C2E30038E4176C7C91C720BB783C00000000BD31C2E3",
                       "TA1RR0000E0C11E799D7E120001000000002AB3274C7AA1D5998DBF7E0000000094987608002AB3274C7AA1D5998DBF7E0000000094987608"]

def send_transponder_message(ssn):
    #Generate Tag Data Message <STX><SSN>D113<Transp Msg><crc><ETX>
    i = random.randint(0,4)
    #Randomly assign a tag to the message
    tag_msg = fake_tag_data_array[i]
    #Applying nMod8+1 to SSN per mGate ICD
    my_packet = str((int(ssn)%8)+1) + "D" + str(len(tag_msg)) + tag_msg
    print ("Sending Transponder Message...")
    print(my_packet)
    #Calculate CRC
    x = str(padded_hex(CRC16Kermit().calculate(str(my_packet)),4)).upper()
    x = x[2:]
    calc_crc = x[2:] + x[:2]
    my_packet = my_packet + calc_crc
    b_array = bytearray()
    b_array.extend(my_packet)
    #Send Bytes out over serial port
    ser.write(b'\x02') #STX
    ser.write(b_array)
    ser.write(b'\x03') #ETX

my_state = "AWAKE" #Default startup state of the state machine
link_state = 0 #0 => Disconnected; 1 => Connected
ssn = "" #Sequence Number Field
byte_array = "" #Array filled with received bytes
control = "" #Control Field
pl_count = 0 #Counter for Count (Packet Length) Field
count_field = "" #Count (Packet Length) Field
crc_count = 0 #Counter for Terminator (CRC)
crc_array = "" #Array filled with CRC bytes
main_ssn = 0 #Send Sequence Number
main_rsn = 0 #Receive Sequence Number
start_time = time.time() #start timer value
end_time = time.time() #end timer value
timeout = 2.0 #2 seconds

while ser.is_open:
    #Perform a timeout check
    end_time = time.time()
    #If timeout is exceeded reset the link
    if (end_time - start_time) >= timeout:
        my_state = "AWAKE"
        link_state = 0
    #Otherwise proceed as normal
    if ser.inWaiting() == 0 and link_state == 0:
        #Send Restart Request every second until we get a response
        if my_state == "AWAKE":
            #LC link is disconnected
            link_state = 0
            ssn = ""
            byte_array = ""
            control = ""
            pl_count = 0
            count_field = ""
            crc_count = 0
            crc_array = ""
            main_ssn = 0
            main_rsn = 0
            #Generate Restart Request
            send_restart_request()
            my_state = "SLEEP_1_SECOND"
            start_time = time.time()
        elif my_state == "SLEEP_1_SECOND":
            #Sleep for 1 Second
            time.sleep(1)
            #Send another Restart request
            my_state = "AWAKE"
            start_time = time.time()
    elif ser.inWaiting() > 0:
        rx_byte = ser.read(1)
        if rx_byte != '':
            ##Looking for a Restart Confirmation <STX>0A000<crc><ETX>
            if rx_byte == b'\x02' and my_state == "AWAKE":
                #LC link is disconnected
                link_state = 0
                ssn = ""
                byte_array = ""
                control = ""
                pl_count = 0
                count_field = ""
                crc_count = 0
                crc_array = ""
                main_ssn = 0
                main_rsn = 0
                my_state = "SSN"
                start_time = time.time()
            ##Get the Sequence Number field
            elif my_state == "SSN":
                ssn = rx_byte.decode("utf-8")
                byte_array = ssn
                my_state = "CONTROL"
                start_time = time.time()
            elif my_state == "CONTROL":
                control = rx_byte.decode("utf-8")
                byte_array = byte_array + control
                my_state = "COUNT"
                start_time = time.time()
            elif my_state == "COUNT":
                pl_count = pl_count + 1
                count_field = count_field + rx_byte.decode("utf-8")
                byte_array = byte_array + rx_byte.decode("utf-8")
                #Count field has a length of 3 bytes
                if pl_count == 3:
                    if link_state == 0:
                        #Restart Confirmation must have a SSN of '0', a count field of '000', and a control field 'A'
                        if ssn == '0' and count_field == "000" and control == 'A' :
                            my_state = "CRC"
                            start_time = time.time()
                        else:
                            print("Invalid message received from Lane Controller...")
                            print("SSN: " + str(ssn) + " Control: " + str(control) + " Count: " + str(count_field))
                            my_state = "AWAKE"
                            link_state = 0
                    else:
                        #ACK must have a count field of '000' and a control field 'A'
                        if count_field == "000" and control == 'A':
                            my_state = "CRC"
                            start_time = time.time()
                        else:
                            print("Invalid message received from Lane Controller...")
                            print("SSN: " + str(ssn) + " Control: " + str(control) + " Count: " + str(count_field))
                            my_state = "AWAKE"
                            link_state = 0               
            elif my_state == "CRC":
                crc_count = crc_count + 1
                crc_array = crc_array + rx_byte.decode("utf-8")
                #Terminator field is a 16 bit CCITT CRC (Kermit) and has length of 4 bytes
                if crc_count == 4:
                    if link_state == 0:
                        my_state = "WAIT_ETX_RC"
                    else:
                        my_state = "WAIT_ETX_ACK"
                    start_time = time.time()
            elif my_state == "WAIT_ETX_RC":
                if rx_byte == b'\x03':
                    #Got ETX so let's calculate CRC and compare it to terminator field
                    x = str(padded_hex(CRC16Kermit().calculate(str(byte_array)),4)).upper()
                    x = x[2:]
                    calc_crc = x[2:] + x[:2]
                    if calc_crc == crc_array:
                        link_state = 1
                        print ("Received Restart Confirmation...")
                        print(byte_array)
                        print("Link Established!")
                        time.sleep(1)
                        main_ssn = 0
                        send_transponder_message(main_ssn)
                        my_state = "GET_ACK"
            elif my_state == "WAIT_ETX_ACK":
                if rx_byte == b'\x03':
                    #Got ETX so let's calculate CRC and compare it to terminator field
                    x = str(padded_hex(CRC16Kermit().calculate(str(byte_array)),4)).upper()
                    x = x[2:]
                    calc_crc = x[2:] + x[:2]
                    if calc_crc == crc_array:
                        link_state = 1
                        print ("Message " + str(main_ssn+1) + " Acknowledged by Lane Controller...")
                        print(byte_array)
                        time.sleep(1)
                        main_ssn = main_ssn + 1
                        send_transponder_message(main_ssn)
                        my_state = "GET_ACK"
            ##Looking for a ACK <STX><SSN>A000<crc><ETX>
            elif rx_byte == b'\x02' and my_state == "GET_ACK":
                ssn = ""
                byte_array = ""
                control = ""
                pl_count = 0
                count_field = ""
                crc_count = 0
                crc_array = ""
                my_state = "SSN"
                start_time = time.time()
            else:
                print(rx_byte)

ser.close()
