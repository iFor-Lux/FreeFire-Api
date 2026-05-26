import json
import os
from google.protobuf.message import Message
from google.protobuf import json_format, message
from Crypto.Cipher import AES
from Configuration.AESConfiguration import MAIN_KEY, MAIN_IV

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Configuration', 'AccountConfiguration.json')

# Load accounts from JSON file
def load_accounts():
    try:
        with open(_CONFIG_PATH, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise Exception(f"AccountConfiguration.json not found at {_CONFIG_PATH}")
    except json.JSONDecodeError:
        raise Exception("Error parsing AccountConfiguration.json")

def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(text: bytes) -> bytes:
    aes = AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV)
    return aes.encrypt(pad(text))
    
def encode_protobuf(data: dict, proto_message: Message) -> bytes:
    """
    Utility function to convert dictionary/data to proto bytes
    
    Args:
        data (dict): Dictionary with proto data
        proto_message (Message): Proto message instance
    
    Returns:
        bytes: Serialized proto data
    
    Raises:
        ValueError: If input is invalid
        Exception: If proto conversion fails
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")
    
    if not isinstance(proto_message, Message):
        raise ValueError("proto_message must be a protobuf Message")
    
    try:
        json_format.ParseDict(data, proto_message)
        return aes_cbc_encrypt(proto_message.SerializeToString())
    except Exception as e:
        raise Exception(f"Proto conversion failed: {str(e)}")

def decode_protobuf(encoded_data: bytes, message_type: message.Message, include_defaults: bool = True):
    """
    Decode protobuf using compiled schema.
    When include_defaults=True (default), fields with default values are included.
    """
    instance = message_type()
    instance.ParseFromString(encoded_data)
    kwargs = {"preserving_proto_field_name": True}
    if include_defaults:
        kwargs["including_default_value_fields"] = True
    return json.loads(json_format.MessageToJson(instance, **kwargs))


def decode_protobuf_full(encoded_data: bytes, message_type: message.Message):
    """
    Decode protobuf with full field preservation.
    Returns both the compiled-proto JSON AND raw wire-format decode.
    
    Returns:
        dict with:
          - "known": parsed via compiled proto (named fields, with defaults)
          - "raw": raw wire-format decode (catches fields NOT in .proto)
          - "all": merged named+raw result with field names applied
    """
    from Utilities.proto_decoder import decode_all as _decode_all
    return _decode_all(encoded_data, message_type)
    