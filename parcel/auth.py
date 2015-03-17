from base64 import b64encode
from base64 import b64decode

from Crypto import Random
from Crypto.Hash import SHA
from Crypto.Cipher import AES
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS


KEY_LENGTH = 4096  # Key size (in bits)
random_gen = Random.new().read


def server_auth(send, recv, key, **opts):
    '''Perform server-side pubkey authentication.

    :param send: Function taking one positional argument, payload to client.
    :param recv: Function taking no positional arguments, payload from client.
    :param key: String serialized server private key.

    Returns the symmetric key and initialization vector.
    '''

    # TODO respond with error on failure
    
    server_key = RSA.importKey(key)
    server_dec = PKCS1_OAEP.new(server_key)

    client_key = RSA.importKey(b64decode(recv(**opts)))
    client_enc = PKCS1_OAEP.new(client_key)

    msg = server_dec.decrypt(b64decode(recv(**opts)))
    msg = SHA.new(msg)
    msg = PKCS1_PSS.new(server_key).sign(msg)
    send(b64encode(msg))
    
    k = Random.new().read(AES.block_size)
    i = Random.new().read(AES.block_size)

    send(b64encode(client_enc.encrypt(k + i)), **opts)

    return k,i


def client_auth(send, recv, key, **opts):
    '''Perform client-side pubkey authentication.

    :param send: Function taking one positional argument, payload to server.
    :param recv: Function taking no positional arguments, payload from server.
    :param key: String serialized server public key.

    Returns the symmetric key and initialization vector.
    '''

    # TODO respond with error on failure
    
    server_key = RSA.importKey(key)
    server_enc = PKCS1_OAEP.new(server_key)
    
    client_key = RSA.generate(KEY_LENGTH, random_gen)
    client_dec = PKCS1_OAEP.new(client_key)

    client_pub = client_key.publickey().exportKey()
    send(b64encode(client_pub), **opts)

    msg = random_gen(4)
    send(b64encode(server_enc.encrypt(msg)), **opts)

    msg = SHA.new(msg)
    res = b64decode(recv())
    if not PKCS1_PSS.new(server_key).verify(msg, res):
        log.debug('Signature failed validation.')
        raise ValueError('Server signature invalid.')

    res = client_dec.decrypt(b64decode(recv(**opts)))
    k,i = res[:len(res)/2], res[len(res)/2:]

    return k,i
