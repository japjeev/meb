import time
import serial
from PyCRC.CRC16Kermit import CRC16Kermit
import sys

try: color = sys.stdout.shell
except AttributeError: raise RuntimeError("Use IDLE")

def get_tag_type(tagtype):
    retval = "Undefined"
    if tagtype == 0:
        retval = "Internal FPT"
    elif tagtype == 1:
        retval = "Exterior FPT"
    elif tagtype == 2:
        retval = "Exterior LPT"
    elif tagtype == 3:
        retval = "LCD Display"
    elif tagtype == 4:
        retval = "CVO"
    elif tagtype == 5:
        retval = "Feedback"
    elif tagtype == 6:
        retval = "HOV"
    return retval

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

ser = serial.Serial(port='COM3', baudrate=19200, timeout=None)
#print("Serial port open? " + str(ser.isOpen()))

my_state = "STX"
ssn_count = 0
pl_count = 0
crc_count = 0
td_count = 0
ssn = ""
payload_length = ""
int_payload_length = 0
crc = ""
control_byte = b'0'
byte_array = ""
crc_array = ""
tag_data_array = ""
start = None
end = None
while True:
    out = ''
    out = ser.read(1)
    if out != '':
        if out == b'\x02' and my_state != "GET_OBU_DATA":
            #print("Received STX - Start of CRQ packet")
            my_state = "SSN"
            start = time.time()
            print("Start time...")
            print(start)
        else:
            if my_state == "SSN":
                ssn_count = ssn_count + 1
                ssn = ssn + out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                if ssn_count == 4:   
                    #print("SSN: " + ssn)
                    my_state = "CONTROL"
            elif my_state == "CONTROL":
                control_byte = out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                #print("Control byte: " + str(control_byte))
                if out.decode("utf-8") == 'Q':
                    #print("Connection Request Packet (CRQ) Received")
                    my_state = "PAYLOAD_LENGTH"
            elif my_state == "PAYLOAD_LENGTH":
                pl_count = pl_count + 1
                payload_length = payload_length + out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                if pl_count == 3:
                    #print("Payload Length: " + payload_length)
                    my_state = "CRC"
            elif my_state == "CRC":
                crc_count = crc_count + 1
                crc = crc + out.decode("utf-8")
                crc_array = crc_array + out.decode("utf-8")
                if crc_count == 4:
                    #print("Received CRC: " + crc)
                    my_state = "WAIT_ETX_CRQ"
            elif my_state == "WAIT_ETX_CRQ":
                if out == b'\x03':
                    #print("Received ETX - End of CRQ packet")
                    x = str(padded_hex(CRC16Kermit().calculate(byte_array),4)).upper()
                    x = x[2:]
                    calc_crc = x[2:] + x[:2]
                    #print("Calculated CRC: " + calc_crc)
                    if crc_array == calc_crc:
                        #print("CRQ Packet CRC Correct")
                        ser.write(b'\x02')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'A')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'2')
                        ser.write(b'3')
                        ser.write(b'4')
                        ser.write(b'0')
                        ser.write(b'\x03')
                        #print("ACK Packet Transmitted")
                        my_state = "GET_OBU_DATA"
                    else:
                        #print("CRQ Packet CRC Error")
                        my_state = "STX"
            elif my_state == "GET_OBU_DATA":
                if out == b'\x02':
                    #print("Received STX - Start of OBU DATA packet")
                    my_state = "GET_SSN"
                    ssn_count = 0
                    pl_count = 0
                    crc_count = 0
                    td_count = 0
                    ssn = ""
                    payload_length = ""
                    control_byte = b'0'
                    byte_array = ""
                    crc_array = ""
                    tag_data_array = ""
            elif my_state == "GET_SSN":
                ssn_count = ssn_count + 1
                ssn = ssn + out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                if ssn_count == 4:   
                    #print("SSN: " + ssn)
                    my_state = "GET_CONTROL"
            elif my_state == "GET_CONTROL":
                control_byte = out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                #print("Control byte: " + str(control_byte))
                if control_byte == 'D':
                    #print("OBU Data Packet Received")
                    my_state = "GET_PAYLOAD_LENGTH"
                elif control_byte == 'X':
                    #print("Transfer Complete Packet Received")
                    my_state = "END_PAYLOAD_LENGTH"
            elif my_state == "GET_PAYLOAD_LENGTH":
                pl_count = pl_count + 1
                payload_length = payload_length + out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                if pl_count == 3:
                    int_payload_length = int(payload_length)
                    #print("Payload Length: " + payload_length + " bytes")
                    my_state = "GET_DATA_BLOB"
            elif my_state == "END_PAYLOAD_LENGTH":
                pl_count = pl_count + 1
                payload_length = payload_length + out.decode("utf-8")
                byte_array = byte_array + out.decode("utf-8")
                if pl_count == 3:
                    #print("Payload Length: " + payload_length)
                    my_state = "END_CRC"
            elif my_state == "GET_DATA_BLOB":
                td_count = td_count + 1
                byte_array = byte_array + out.decode("utf-8")
                tag_data_array = tag_data_array + out.decode("utf-8")
                if td_count == int_payload_length:
                    #print("Application payload received")
                    tmp_array = tag_data_array.split(';')
                    time_stamp = tmp_array[0]
                    bin_str = bin(int(tmp_array[len(tmp_array)-1], 16))[2:].zfill(8)
                    hdr = int(bin_str[0:3],2)
                    tagtype = int(bin_str[3:6],2)
                    appid = int(bin_str[6:9],2)
                    groupid = int(bin_str[9:16],2)
                    agencyid = int(bin_str[16:23],2)
                    serialnum = str(int(bin_str[23:47],2))
                    if hdr == 7 and appid == 1 and groupid == 65 and tagtype != 6: ## Non-HOV tag
                        print_str = time_stamp + ", Serial#:" + serialnum + ", Tag type:" + get_tag_type(tagtype) + ", Agency#:" + str(agencyid)
                        color.write(print_str + ' \n',"ERROR")
                    elif hdr == 7 and appid == 1 and groupid == 65 and tagtype == 6: ## HOV tag
                        ##Japjeev's tag with history bit HOT and switch HOT
                        ##F8C1143C4EF612000000000000146975785521234BABC0010000000067E8643F
                        ##Japjeev's tag with history bit HOT and switch HOV
                        ##F8C1143C4EF612000000000000146975785521234BABC0010200000067E8EF7F 
                        ##print_str = tmp_array[len(tmp_array)-1]
                        switchbit = int(bin_str[198:199],2)
                        if switchbit == 1:
                            print_str = time_stamp + ", Serial#:" + serialnum + ", Tag type:" + get_tag_type(tagtype) + ", Agency#:" + str(agencyid) + ", Switch: HOV"
                            color.write(print_str + ' \n',"KEYWORD")
                        else:
                            print_str = time_stamp + ", Serial#:" + serialnum + ", Tag type:" + get_tag_type(tagtype) + ", Agency#:" + str(agencyid) + ", Switch: HOT"
                            color.write(print_str + ' \n',"ERROR")
                    else:
                        color.write("Invalid tag detected" + ' \n',"KEYWORD")
                    my_state = "GET_CRC"
            elif my_state == "GET_CRC":
                crc_count = crc_count + 1
                crc_array = crc_array + out.decode("utf-8")
                if crc_count == 4:
                    #print("Received CRC: " + crc_array)
                    my_state = "WAIT_ETX_DATA_PACKET"
            elif my_state == "END_CRC":
                crc_count = crc_count + 1
                crc_array = crc_array + out.decode("utf-8")
                if crc_count == 4:
                    #print("Received CRC: " + crc_array)
                    my_state = "WAIT_ETX_TC_PACKET"
            elif my_state == "WAIT_ETX_DATA_PACKET":
                if out == b'\x03':
                    #print("Received ETX - End of OBU DATA packet")
                    x = str(padded_hex(CRC16Kermit().calculate(byte_array),4)).upper()
                    x = x[2:]
                    calc_crc = x[2:] + x[:2]
                    #print("Calculated CRC: " + calc_crc)
                    if crc_array == calc_crc:
                        #print("OBU DATA Packet CRC Correct")
                        ack_packet = ssn + "A000"
                        x = str(padded_hex(CRC16Kermit().calculate(ack_packet),4)).upper()
                        x = x[2:]
                        calc_crc = x[2:] + x[:2]
                        ser.write(b'\x02')
                        ser.write(bytes(ssn[0],'utf_8'))
                        ser.write(bytes(ssn[1],'utf_8'))
                        ser.write(bytes(ssn[2],'utf_8'))
                        ser.write(bytes(ssn[3],'utf_8'))
                        ser.write(b'A')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(bytes(calc_crc[0],'utf_8'))
                        ser.write(bytes(calc_crc[1],'utf_8'))
                        ser.write(bytes(calc_crc[2],'utf_8'))
                        ser.write(bytes(calc_crc[3],'utf_8'))
                        ser.write(b'\x03')
                        #print("ACK Packet Transmitted")
                        my_state = "GET_OBU_DATA"
                    else:
                        #print("OBU DATA Packet CRC Error")
                        break
            elif my_state == "WAIT_ETX_TC_PACKET":
                if out == b'\x03':
                    #print("Received ETX - End of Transfer Complete packet")
                    x = str(padded_hex(CRC16Kermit().calculate(byte_array),4)).upper()
                    x = x[2:]
                    calc_crc = x[2:] + x[:2]
                    #print("Calculated CRC: " + calc_crc)
                    if crc_array == calc_crc:
                        #print("Transfer Complete Packet CRC Correct")
                        ack_packet = ssn + "A000"
                        x = str(padded_hex(CRC16Kermit().calculate(ack_packet),4)).upper()
                        x = x[2:]
                        calc_crc = x[2:] + x[:2]
                        ser.write(b'\x02')
                        ser.write(bytes(ssn[0],'utf_8'))
                        ser.write(bytes(ssn[1],'utf_8'))
                        ser.write(bytes(ssn[2],'utf_8'))
                        ser.write(bytes(ssn[3],'utf_8'))
                        ser.write(b'A')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(b'0')
                        ser.write(bytes(calc_crc[0],'utf_8'))
                        ser.write(bytes(calc_crc[1],'utf_8'))
                        ser.write(bytes(calc_crc[2],'utf_8'))
                        ser.write(bytes(calc_crc[3],'utf_8'))
                        ser.write(b'\x03')
                        #print("ACK Packet Transmitted")
                        my_state = "STX"
                        ssn_count = 0
                        pl_count = 0
                        crc_count = 0
                        td_count = 0
                        ssn = ""
                        payload_length = ""
                        int_payload_length = 0
                        crc = ""
                        control_byte = b'0'
                        byte_array = ""
                        crc_array = ""
                        tag_data_array = ""
                        end = time.time()
                        print("End time...")
                        print(end)
                        print("Run time...")
                        print(end - start)
    
                    else:
                        #print("Transfer Complete Packet CRC Error")
                        break
            else:
                print(out)
                print(my_state)

ser.close()
#print("Serial port open? " + str(ser.isOpen()))
