import asyncio
import struct

from os import urandom

from Crypto.Cipher import AES

from bleak import BleakClient, BleakScanner


from bleak.backends.characteristic import BleakGATTCharacteristic

import logging

_LOGGER = logging.getLogger("awox")



PAIR_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1914'
COMMAND_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1912'
STATUS_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1911'
OTA_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1913'
SERV_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1913'

C_POWER = 0xd0

def notification_handler(characteristic: BleakGATTCharacteristic , data: bytearray):
    """Simple notification handler which prints the data received."""
    print("notification :: ", characteristic.description, " :: ", data)

class AwoxMeshLight:
    def __init__ (self, mac : str ) -> None:
        """
        Args :
            mac: The light's MAC address as a string in the form AA:BB:CC:DD:EE:FF
            mesh_name: The mesh name as a string.
            mesh_password: The mesh password as a string.
        """
        _LOGGER.info("Starting Awox lights control")
        
        self.mac = mac
        self.mesh_id = 0
        #self.btdevice = btle.Peripheral ()
        self.session_key = None
        self.command_char = None

        mesh_name = ""
        mesh_password = ""

        mesh_name = mesh_name.encode ()
        mesh_password = mesh_password.encode ()

        # Light status
        self.white_brightness = None
        self.white_temp = None
        self.color_brightness = None
        self.red = None
        self.green = None
        self.blue = None
        self.mode = None
        self.status = None
        
        self.is_on = False
        self.connected = None
        self.brightness = None

        self._attr_device_info = ...  # For automatic device registration
        self._attr_unique_id = ...

        
        

    @staticmethod
    def encrypt (key, value):
        assert (len(key) == 16)
        k = bytearray (key)
        val = bytearray(value.ljust (16, b'\x00'))
        k.reverse ()
        val.reverse ()
        cipher = AES.new(bytes(k), AES.MODE_ECB)
        
        val = bytearray(cipher.encrypt(bytes(val)))
        val.reverse ()

        return val

    
    @staticmethod
    def make_checksum (key, nonce, payload):
        """
        Args :
            key: Encryption key, 16 bytes
            nonce:
            payload: The unencrypted payload.
        """
        base = nonce + bytearray ([len(payload)])
        base = base.ljust (16, b'\x00')
        check =  AwoxMeshLight.encrypt (key, base)

        for i in range (0, len (payload), 16):
            check_payload = bytearray (payload[i:i+16].ljust (16, b'\x00'))
            check = bytearray([ a ^ b for (a,b) in zip(check, check_payload) ])
            check =  AwoxMeshLight.encrypt (key, check)

        return check
    

    @staticmethod
    def make_session_key (mesh_name, mesh_password, session_random, response_random):
        random = session_random + response_random
        m_n = bytearray (mesh_name.ljust (16, b'\x00'))
        m_p = bytearray (mesh_password.ljust (16, b'\x00'))
        name_pass = bytearray([ a ^ b for (a,b) in zip(m_n, m_p) ])
        key = AwoxMeshLight.encrypt (name_pass, random)
        return key

    @staticmethod
    def crypt_payload (key, nonce, payload):
        """
        Used for both encrypting and decrypting.

        """
        base = bytearray(b'\x00' + nonce)
        base = base.ljust (16, b'\x00')
        result = bytearray ()

        for i in range (0, len (payload), 16):
            enc_base = AwoxMeshLight.encrypt (key, base)
            result += bytearray ([ a ^ b for (a,b) in zip (enc_base, bytearray (payload[i:i+16]))])
            base[0] += 1

        return result


    @staticmethod
    def make_command_packet (key, address, dest_id, command, data):
        """
        Args :
            key: The encryption key, 16 bytes.
            address: The mac address as a string.
            dest_id: The mesh id of the command destination as a number.
            command: The command as a number.
            data: The parameters for the command as bytes.
        """
        # Sequence number, just need to be different, idea from https://github.com/nkaminski/csrmesh
        s  = urandom (3)

        # Build nonce
        a = bytearray.fromhex(address.replace (":",""))
        #print("a :: ", a)
        a.reverse()
        #print("a :: ", a)
        nonce = bytes(a[0:4] + b'\x01' + s)

        # Build payload
        dest = struct.pack ("<H", dest_id)
        payload = (dest + struct.pack('B', command) + b'\x60\x01' + data).ljust(15, b'\x00')

        # Compute checksum
        check = AwoxMeshLight.make_checksum (key, nonce, payload)

        # Encrypt payload
        payload = AwoxMeshLight.crypt_payload (key, nonce, payload)

        #print("payload :: ", payload)
        #print("check :: ", check)
        #print("s :: ", s)
        # Make packet
        packet = s + check[0:2] + payload
        #print("packet :: ", packet)
        return packet
    
    @staticmethod
    def make_pair_packet (mesh_name, mesh_password, session_random):
        m_n = bytearray (mesh_name.ljust (16, b'\x00'))
        m_p = bytearray (mesh_password.ljust (16, b'\x00'))
        s_r = session_random.ljust (16, b'\x00')
        name_pass = bytearray ([ a ^ b for (a,b) in zip(m_n, m_p) ])
        enc = AwoxMeshLight.encrypt (s_r ,name_pass)
        packet = bytearray(b'\x0c' + session_random) # 8bytes session_random
        packet += enc[0:8]
        return packet

    

    @staticmethod
    async def connect_to_device(switch):


        _LOGGER.info("Searching devices...")
        devices = await BleakScanner.discover()
        i=0
        for device in devices:
            i = i + 1
            _LOGGER.info("%s :: %s ",i, device)
            if device.address == "A4:C1:38:77:2A:18":
                selDevice = device
                _LOGGER.info("Found device: ",device)
                break


        try:

            _LOGGER.info("Connecting to device... %s", selDevice.address)
            async with BleakClient(selDevice,disconnected_callback=None,timeout=30) as client:

                _LOGGER.info("Connecting... %s", selDevice.name)

                if client.is_connected:
                    _LOGGER.info("Connected: ",client.address)
        
            
                
                    
                    
                    pair_char = await client.read_gatt_char(PAIR_CHAR_UUID)
                    _LOGGER.info("Pair characteristic data : {0}".format(pair_char) , " :: ", pair_char)


                    #name = "F8GwIEDa"
                    _LOGGER.info ("client :: ", client)
                    name = 'F8GwIEDa'
                    key = "31617080"
                    # Converter as strings em objetos bytearray
                    name = name.encode()
                    key = key.encode()
                            
                    # Gerar um número aleatório de 8 bytes
                    session_random =  urandom(8)
                
                
                
                    #_LOGGER.info("Name: ", name)
                    #_LOGGER.info("Key: ", key)
                    #_LOGGER.info("Session random: ")
                    #_LOGGER.info(session_random)

                    # Chamar a função make_pair_packet
                    packet = AwoxMeshLight.make_pair_packet(name, key, session_random)

                    _LOGGER.info("packet created: {0}".format(packet))
                    resp = await client.write_gatt_char(PAIR_CHAR_UUID, packet,response=True)
                    _LOGGER.info("Pair response: {0}".format(resp))

                    status_char = await client.read_gatt_char(STATUS_CHAR_UUID)
                    _LOGGER.info("Status characteristic: {0}".format(status_char))
                    resp = await client.write_gatt_char (STATUS_CHAR_UUID,b'\x01',response=True)
                    _LOGGER.info("Status response: {0}".format(resp))

                    
            
                    pair_char = await client.read_gatt_char(PAIR_CHAR_UUID)
                    _LOGGER.info("Pair resp data: ",pair_char[0])

                    if pair_char[0] == 0xd :
                        session_key = AwoxMeshLight.make_session_key (name, key, session_random, pair_char[1:9])
                        _LOGGER.info("Sending command...", len(session_key))
                        _LOGGER.info ("Session key : %s", repr (session_key))
                        _LOGGER.info("Connected.")

                        #delay 5 seconds
                        await asyncio.sleep(2.0)

                        await AwoxMeshLight.writeCommand (C_POWER, switch ,session_key,client)
                        disc = await client.disconnect ()
                        _LOGGER.info("Disconnected: {0}".format(disc))

                        #packet = AwoxMeshLight.make_command_packet (session_key, "A4:C1:38:64:4B:2F", 0, 208, b"\x01")
                        #print("packet created: ",packet)
                        #cmd_char =  await client.write_gatt_char(COMMAND_CHAR_UUID,packet,True )
                        #print("cmd resp data: {0}".format(cmd_char))
                    else :
                        if pair_char[0] == 0xe :
                            _LOGGER.info("Auth error : check name and password.")
                        else :
                            _LOGGER.info("Unexpected pair value : %s", repr (pair_char))
                        await client.disconnect ()
                        return False
        except Exception as e:
            _LOGGER.info("Error: {0}".format(e))
            #await AwoxMeshLight.connect_to_device()
            return False


    async def writeCommand (command, data,session_key,client ,dest = None):
        """
        Args:
            command: The command, as a number.
            data: The parameters for the command, as bytes.
            dest: The destination mesh id, as a number. If None, this lightbulb's
                mesh id will be used.
        """
        assert (session_key)
        
        #def make_command_packet (key, address, dest_id, command, data):
        packet = AwoxMeshLight.make_command_packet (session_key, client.address, 0, command, data)

        _LOGGER.info("packet created: ",packet)

        read = await client.read_gatt_char(COMMAND_CHAR_UUID)
        _LOGGER.info("read: ",read)

        resp = await client.write_gatt_char(COMMAND_CHAR_UUID, packet, True)
        _LOGGER.info("cmd resp data: ",resp)

        readresp = await client.read_gatt_char(COMMAND_CHAR_UUID)
        _LOGGER.info("read resp: ",readresp)



    @property
    async def async_is_on(self):
        """If the switch is currently on or off."""
        _LOGGER.info("is_on :: %s",self._is_on)

        return self._is_on

    async def turn_on(self):
        _LOGGER.info("Turn on...")
        await self.connect_to_device(b'\x01')
        self._is_on = True

    async def turn_off(self):
        _LOGGER.info("Turn off...")
        await self.connect_to_device(b'\x00')
        self._is_on = False