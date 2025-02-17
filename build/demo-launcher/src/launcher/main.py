from contextlib import asynccontextmanager
import os
import sys
from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncssh
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import jwt
from datetime import datetime, timedelta
from typing import Annotated, Any, Optional
from jose.utils import base64url_encode
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import yaml
from xmlrpc.client import ServerProxy
from launcher.config import (
    UnsafeSSHClientPool,
    UnsafeSSHUserKeys,
    UnsafeServiceAccount,
    UnsafeSettings,
)

from launcher.pwd_command import PwdCommand


sys.path.append("../../../src")
sys.path.append("../")
from firecrest.config import FileSystem
from lib.ssh_clients.ssh_client import SSHClient
from firecrest.config import FileSystemDataType


keys = {}


@asynccontextmanager
async def lifespan(app: FastAPI):

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    keys["private_key_pem"] = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    keys["public_numbers"] = public_numbers
    keys["kid"] = "42"  # unique key identifier

    print(
        """
██████╗ ███████╗███╗   ███╗ ██████╗                                
██╔══██╗██╔════╝████╗ ████║██╔═══██╗                               
██║  ██║█████╗  ██╔████╔██║██║   ██║                               
██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║                               
██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝                               
╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝                                
██╗      █████╗ ██╗   ██╗███╗   ██╗ ██████╗██╗  ██╗███████╗██████╗ 
██║     ██╔══██╗██║   ██║████╗  ██║██╔════╝██║  ██║██╔════╝██╔══██╗
██║     ███████║██║   ██║██╔██╗ ██║██║     ███████║█████╗  ██████╔╝
██║     ██╔══██║██║   ██║██║╚██╗██║██║     ██╔══██║██╔══╝  ██╔══██╗
███████╗██║  ██║╚██████╔╝██║ ╚████║╚██████╗██║  ██║███████╗██║  ██║
╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
    """
    )

    print("Navigte to http://localhost:8080/ to get started!\n\n")

    yield


app = FastAPI(lifespan=lifespan)
security = HTTPBasic(auto_error=False)
settings = UnsafeSettings()


def get_jwk():
    jwk_data = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": keys["kid"],
        "n": base64url_encode(
            keys["public_numbers"].n.to_bytes(
                (keys["public_numbers"].n.bit_length() + 7) // 8, byteorder="big"
            )
        ),
        "e": base64url_encode(
            keys["public_numbers"].e.to_bytes(
                (keys["public_numbers"].e.bit_length() + 7) // 8, byteorder="big"
            )
        ),
    }
    return jwk_data


def generate_token(username: str):
    expiration = datetime.utcnow() + timedelta(days=360)
    payload = {
        "sub": f"{username}-client",
        "name": username,
        "username": username,
        "preferred_username": username,
        "scope": "firecrest-v2 profile email",
        "exp": expiration,
    }
    headers = {"kid": keys["kid"]}
    token = jwt.encode(
        payload, keys["private_key_pem"], algorithm="RS256", headers=headers
    )
    return token


@app.post("/token")
def get_token(
    credentials: Annotated[Optional[HTTPBasicCredentials], Depends(security)],
    grant_type: Optional[str] = Form(default=None),
    client_id: Optional[str] = Form(default=None),
    client_secret: Optional[str] = Form(default=None),
):
    username: str = None
    if client_id:
        username = client_id
    if credentials and credentials.username:
        username = credentials.username

    token = generate_token(username)

    return {"access_token": token, "token_type": "bearer"}


@app.get("/certs")
def download_certificate():
    return {"keys": [get_jwk()]}


@app.get("/boot")
def get_boot():

    username = next(iter(settings.ssh_credentials))

    dump: dict[str, Any] = settings.model_dump()
    settings_file = os.getenv("YAML_CONFIG_FILE", None)
    with open(settings_file, "w") as yaml_file:
        yaml.dump(dump, yaml_file)

    server = ServerProxy("http://dummy:dummy@localhost:9001/RPC2")

    state = server.supervisor.getProcessInfo("firecrest")

    if state["statename"] == "RUNNING":
        server.supervisor.stopProcess("firecrest")

    server.supervisor.startProcess("firecrest")

    token = generate_token(username)

    return {"message": "Firecrest v2 started successfully.", "access_token": token}


class Credentials(BaseModel):
    username: str
    private_key: str
    public_cert: Optional[str] = None


@app.post("/credentials")
def credentials(credentials: Credentials):

    if not credentials.username:
        raise HTTPException(status_code=400, detail="Provide a valid username")

    try:
        asyncssh.import_private_key(credentials.private_key)
        if credentials.public_cert:
            asyncssh.import_certificate(credentials.public_cert)

            ssh_credential = UnsafeSSHUserKeys(
                **{
                    "private_key": credentials.private_key,
                    "public_cert": credentials.public_cert,
                }
            )
            settings.ssh_credentials.clear()
            settings.ssh_credentials[credentials.username] = ssh_credential

    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    return {"message": "Credentials saved successfully."}


class SSHConnection(BaseModel):
    hostname: str
    hostport: int
    proxyhost: Optional[str] = None
    proxyport: Optional[int] = None


@app.post("/sshconnection")
async def ssh_connection(ssh_connection: SSHConnection):

    username = next(iter(settings.ssh_credentials))
    try:
        sshkey_private = asyncssh.import_private_key(
            settings.ssh_credentials[username].private_key
        )
        sshkey_cert_public = ()
        if settings.ssh_credentials[username].public_cert:
            sshkey_cert_public = asyncssh.import_certificate(
                settings.ssh_credentials[username].public_cert
            )
        options = asyncssh.SSHClientConnectionOptions(
            username=username,
            client_keys=[sshkey_private],
            client_certs=[sshkey_cert_public],
            known_hosts=None,
        )

        proxy = ()
        if ssh_connection.proxyhost:
            proxy = await asyncssh.connect(
                host=ssh_connection.proxyhost,
                port=ssh_connection.proxyport,
                options=options,
            )

        conn = await asyncssh.connect(
            host=ssh_connection.hostname,
            port=ssh_connection.hostport,
            options=options,
            tunnel=proxy,
        )
        client = SSHClient(conn)
        pwd = PwdCommand()
        user_home = await client.execute(pwd)

        file_system = FileSystem(
            **{
                "path": user_home,
                "data_type": FileSystemDataType.users,
                "default_work_dir": True,
            }
        )

        demo_cluster = settings.clusters[0]
        ssh_client_pool = UnsafeSSHClientPool(
            **{
                "host": ssh_connection.hostname,
                "port": ssh_connection.hostport,
                "proxy_host": ssh_connection.proxyhost,
                "proxy_port": ssh_connection.proxyport,
            }
        )
        service_account = UnsafeServiceAccount(**{"client_id": username, "secret": ""})

        demo_cluster.ssh = ssh_client_pool
        demo_cluster.service_account = service_account
        demo_cluster.file_systems = [file_system]

    except Exception as e:
        raise HTTPException(status_code=400, detail=repr(e)) from e

    return {"message": "SSH connection saved successfully.", "user_home": user_home}


app.mount(
    "/",
    StaticFiles(directory="/app/launcher/static", html=True),
    name="static-play",
)
