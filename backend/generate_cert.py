"""
Generate self-signed certificate for HTTPS
"""
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone, timedelta

def generate_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'), x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'State'), x509.NameAttribute(NameOID.LOCALITY_NAME, 'City'), x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'FRCAS'), x509.NameAttribute(NameOID.COMMON_NAME, '192.168.43.97')])
    cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)).not_valid_after(datetime.now(timezone.utc) + timedelta(days=365)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address('192.168.43.97')), x509.DNSName('localhost')]), critical=False).sign(key, hashes.SHA256(), default_backend())
    with open('cert.pem', 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open('key.pem', 'wb') as f:
        f.write(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()))
if __name__ == '__main__':
    generate_cert()
