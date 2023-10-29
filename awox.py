import asyncio
import struct

from os import urandom

from Crypto.Cipher import AES

from bleak import BleakClient, BleakScanner


from bleak.backends.characteristic import BleakGATTCharacteristic

import logging

_LOGGER = logging.getLogger("awox")

from .const import DOMAIN, CONF_MESH_NAME, CONF_MESH_KEY

from homeassistant.core import HomeAssistant


from homeassistant.components import bluetooth

PAIR_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1914'
COMMAND_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1912'
STATUS_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1911'
OTA_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1913'
SERV_CHAR_UUID = '00010203-0405-0607-0809-0a0b0c0d1913'

C_POWER = 0xd0


class AwoxMeshLight:
    def __init__ (self, hass: HomeAssistant, mesh_name: str, mesh_password: str, mesh_long_term_key: str):
        """
        Args :
            mac: The light's MAC address as a string in the form AA:BB:CC:DD:EE:FF
            mesh_name: The mesh name as a string.
            mesh_password: The mesh password as a string.
        """
     

        _LOGGER.info("Starting Awox lights control")
        
        self.mac = "A4:C1:38:77:2A:18"
        self.mesh_id = 0

        self._mesh_name = mesh_name
        self.mesh_password = mesh_password
        self.mesh_long_term_key = mesh_long_term_key

        self.session_key = None
        self.command_char = None


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
    async def connect_to_device(ble_device, switch, awox_name, awox_pass):

        _LOGGER.info("Device to connect :: %s", ble_device)
    
        try:
            async with BleakClient(ble_device ,disconnected_callback=None,timeout=15) as client:

                _LOGGER.info("Connecting to %s...", ble_device)

                if client.is_connected:
                    _LOGGER.info("Connected to : ", client.address)                    
                
                    pair_char = await client.read_gatt_char(PAIR_CHAR_UUID)

                    name = awox_name
                    key = awox_pass

                    name = name.encode()
                    key = key.encode()
                            
                    # Gerar um número aleatório de 8 bytes
                    session_random =  urandom(8)
                
                    packet = AwoxMeshLight.make_pair_packet(name, key, session_random)

                    resp = await client.write_gatt_char(PAIR_CHAR_UUID, packet,response=True)

                    status_char = await client.read_gatt_char(STATUS_CHAR_UUID)

                    resp = await client.write_gatt_char (STATUS_CHAR_UUID,b'\x01',response=True)
            
                    pair_char = await client.read_gatt_char(PAIR_CHAR_UUID)

                    if pair_char[0] == 0xd :
                        session_key = AwoxMeshLight.make_session_key (name, key, session_random, pair_char[1:9])
                        
                        _LOGGER.info("Paired.")

                        #delay 5 seconds
                        await asyncio.sleep(2.0)

                        await AwoxMeshLight.writeCommand (C_POWER, switch ,session_key,client)
                        disc = await client.disconnect ()
                        _LOGGER.info("Disconnected: {0}".format(disc))

                        return True
                        
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
        _LOGGER.info("packet send to : %s ",client.address)

        await client.read_gatt_char(COMMAND_CHAR_UUID)
        await client.write_gatt_char(COMMAND_CHAR_UUID, packet, True)
        await client.read_gatt_char(COMMAND_CHAR_UUID)

    @property
    async def async_is_on(self):
        """If the switch is currently on or off."""
        _LOGGER.info("is_on :: %s",self._is_on)

        return self._is_on
