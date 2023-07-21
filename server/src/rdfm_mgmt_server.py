import os
import jwt
import uuid
import time
from flask import Flask, request, send_file, Response
from threading import Thread
from server import Server, FileTransfer
from rdfm_mgmt_communication import wait_at_most
from request_models import (
    ListRequest,
    InfoDeviceRequest,
    UpdateDeviceRequest,
    ProxyDeviceRequest,
    Alert,
    DownloadRequest,
    UploadRequest,
    Request
)

from typing import Optional
from werkzeug import local
http_request = local.LocalProxy

app = Flask(__name__)
global server


def get_device_file_dir(device_name: str) -> Optional[str]:
    """Checks where files that are uploaded/downloaded from device are
    in server transferred files cache directory.

    Args:
        device_name: Device name

    Returns:
        path to device directory in server transferred files cache
    """
    assert device_name is not None
    device_file_dir = os.path.join(
        os.path.abspath(app.config['UPLOAD_FOLDER']),
        device_name)
    return device_file_dir


def new_file_transfer(device_name: str,
                      device_filepath: str) -> Alert:
    """Creates new file transfer for device if it is possible

    Args:
        device_name: Name of the device to upload/download files
        device_filepath: Path on device where file will
            be downloaded/uploaded from

    Returns:
        Response about result of creating new transfer
    """
    # Check that device is connected
    if device_name not in server.connected_devices:
        return Alert(alert={  # type: ignore
            'error': 'Device not found'
        })
    device = server.connected_devices[device_name]

    # Create file transfer with random cache filename
    cache_filename = str(uuid.uuid4())
    while cache_filename in server.file_transfers:
        cache_filename = str(uuid.uuid4())
    cache_device_dir: Optional[str] = get_device_file_dir(device.name)
    assert cache_device_dir is not None
    server.file_transfers[cache_filename] = FileTransfer(
                                                    device,
                                                    device_filepath,
                                                    os.path.join(
                                                        cache_device_dir,
                                                        cache_filename
                                                    ))
    return Alert(alert={  # type: ignore
        'message': 'New file transfer',
        'filename': cache_filename
    })


def upload_file(request,
                filename: str) -> Optional[Alert]:
    print('xxxxx', type(request))
    """Wrapper to avoid boilerplate code while uploading file as user and
    as a device client

    Args:
        request: HTTP request that was sent
        filename: Server cache filename

    Returns:
        Alert if upload failed
    """
    file = request.files['file']
    if file.filename == '':
        return None
    if file:
        try:
            # Find/create device's directory in server cache
            cache_device_dir = get_device_file_dir(
                                server.file_transfers[filename].device.name)
            if not cache_device_dir:
                return None
            assert cache_device_dir is not None
            device_file_dir = os.path.abspath(cache_device_dir)
            if not os.path.exists(device_file_dir):
                os.makedirs(device_file_dir)
                print('Created directory', device_file_dir)

            # Generate tmp filename
            file.save(os.path.join(device_file_dir, filename))
            print('File uploaded at',
                  os.path.join(device_file_dir, filename)
                  )
            server.file_transfers[filename].uploaded = True

        except Exception as e:
            error_msg = f'Error saving file, {str(e)}'
            print(error_msg)
            return Alert(alert={  # type: ignore
                'error': error_msg
            })
    return None


def download_file(filename: str) -> Request | Response:
    """Wrapper to avoid boilerplate code while downloading file as user and
    as a device client

    Args:
        device_name: Optional device name (if it was provided user sent it)

    Returns:
        reply to request or sends a file
    """

    transfer = server.file_transfers[filename]
    print('Waiting for file', filename, 'to be uploaded...')

    # Wait for device to start upload
    if not wait_at_most(30, 0.5, lambda: transfer.started):
        return Alert(alert={  # type: ignore
            'error': 'Device timeout'
        })

    # Wait until file uploads
    while not transfer.uploaded and not transfer.error:
        time.sleep(1)
    if transfer.error:
        print('Device sent back an error')
        return Alert(alert={  # type: ignore
            'error': transfer.error_msg
        })

    device_file_dir = get_device_file_dir(transfer.device.name)
    if not device_file_dir:
        return Alert(alert={  # type: ignore
            'error': f'No file to download'
        })

    filepath = os.path.join(device_file_dir, filename)
    print('Sending', filepath)
    return send_file(filepath)


@app.route('/upload', methods=['POST'])  # Device endpoint
def upload() -> str:
    try:
        decoded = jwt.decode(request.form['jwt'], server.jwt_secret,
                             algorithms=["HS256"])

        # Find matching file transfer
        filename: Optional[str] = None
        for k, v in server.file_transfers.items():
            if (v.device.name == decoded['name'] and
                    v.device_filepath == request.form['file_path']):
                filename = k
                break

        if not filename:
            error_msg = 'Error, no matching transfer found'
            print(error_msg)
            return Alert(alert={  # type: ignore
                'error': error_msg
            }).model_dump_json()
        transfer = server.file_transfers[filename]
        transfer.started = True

        if 'error' in request.form:
            print('Device sent error')
            transfer.error = True
            transfer.error_msg = request.form['error']
            del server.file_transfers[filename]
            return Alert(alert={  # type: ignore
                'message': 'File upload cancelled'
            }).model_dump_json()

        res: Optional[Alert] = upload_file(request, filename)
        if res:
            return res.model_dump_json()

        server.file_transfers[filename].uploaded = True
        print(filename, 'uploaded!')
        del server.file_transfers[filename]
        return Alert(alert={  # type: ignore
            'message': 'Uploaded file'
        }).model_dump_json()
    except Exception as e:
        error_msg = f'Error uploading file: {str(e)}'
        print(error_msg)
        try:
            assert filename is not None
            del server.file_transfers[filename]
        except Exception:
            pass
        return Alert(alert={  # type: ignore
            'error': error_msg
        }).model_dump_json()


@app.route('/download/<filename>', methods=['GET'])  # Device endpoint
def download(filename):
    res = download_file(filename)
    if isinstance(res, Request):
        return res.model_dump_json()
    return res


@app.route('/device/<device_name>/upload', methods=['POST'])  # Client endpoint
def upload_device(device_name) -> str:
    res: Alert = new_file_transfer(device_name, request.form['file_path'])
    if 'error' in res.alert:
        return res.model_dump_json()

    filename: str = res.alert['filename']
    if not filename:
        return Alert(alert={  # type: ignore
            'error': 'File upload failed'
        }).model_dump_json()

    device = server.connected_devices[device_name]
    # Check that device has capabilities to handle file transfer
    if not device.can_handle_request('download'):
        del server.file_transfers[filename]
        return Alert(alert={  # type: ignore
            'error': (f"Requested device doesn't provide necessary"
                      "capabilities:"),
            "requested_capabilities":
                device.required_capabilities['download']}
        ).model_dump_json()

    upload_res: Optional[Alert] = upload_file(request, filename)
    if upload_res:
        return upload_res.model_dump_json()
    server.file_transfers[filename].started = True

    # Send request to device so it downloads this file
    device.send(DownloadRequest(  # type: ignore
        file_path=request.form['file_path'],
        url=(request.url_root + 'download/' + filename))
    )

    return Alert(alert={  # type: ignore
        'message': 'Uploaded file to device'
    }).model_dump_json()


@app.route('/device/<device_name>/download',  # Client endpoint
           methods=['GET'])
def download_device(device_name) -> str | Response:
    res: Alert = new_file_transfer(device_name, request.form['file_path'])
    if 'error' in res.alert:
        return res.model_dump_json()

    filename: str = res.alert['filename']
    if not filename:
        return Alert(alert={  # type: ignore
            'error': 'File download failed'
        }).model_dump_json()

    device = server.connected_devices[device_name]
    # Check that device has capabilities to handle file transfer
    if not device.can_handle_request('upload'):
        del server.file_transfers[filename]
        return Alert(alert={  # type: ignore
            'error': (f"Requested device doesn't provide necessary"
                      "capabilities:"),
            "requested_capabilities":
                device.required_capabilities['upload']}
        ).model_dump_json()

    # Send request to device so it uploads this file
    device.send(UploadRequest(  # type: ignore
        file_path=request.form['file_path']
    ))

    download_res = download_file(filename)
    if isinstance(download_res, Request):
        return download_res.model_dump_json()
    return download_res


@app.route('/')
def index():
    response = server.handle_request(ListRequest())
    assert response is not None
    return response.model_dump_json()


@app.route('/device/<device_name>', methods=['GET'])
def device_metadata(device_name: str):
    response = server.handle_request(
        InfoDeviceRequest(device_name=device_name)  # type: ignore
    )
    assert response is not None
    return response.model_dump_json()


@app.route('/device/<device_name>/update')
def device_update(device_name: str):
    response = server.handle_request(
        UpdateDeviceRequest(device_name=device_name)  # type: ignore
    )
    assert response is not None
    return response.model_dump_json()


@app.route('/device/<device_name>/proxy')
def device_proxy(device_name: str):
    response = server.handle_request(
        ProxyDeviceRequest(device_name=device_name)  # type: ignore
    )
    assert response is not None
    return response.model_dump_json()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='rdfm-mgmt-shell server instance.')
    parser.add_argument('-hostname', type=str, default='127.0.0.1',
                        help='ip addr or domain name of the host')
    parser.add_argument('-port', metavar='p', type=int, default=1234,
                        help='listening port')
    parser.add_argument('-http_port', metavar='hp', type=int, default=5000,
                        help='listening port')
    parser.add_argument('-no_ssl', action='store_false', dest='encrypted',
                        help='turn off encryption')
    parser.add_argument('-cert', type=str, default='./certs/SERVER.crt',
                        help='server cert file')
    parser.add_argument('-key', type=str, default='./certs/SERVER.key',
                        help="""server cert key file""")
    parser.add_argument('-database', metavar='db', type=str,
                        default='devices.db',
                        help='filepath to store device database')
    parser.add_argument('-cache_dir', type=str, default='server_file_cache',
                        help='file transfer cache directory')
    parser.add_argument('-jwt_secret', type=str,
                        default=os.environ['JWT_SECRET'],
                        help="""JWT secret key, if not provided it will
                            be read from $JWT_SECRET env var""")
    args = parser.parse_args()

    server = Server(args.hostname, args.port,
                    args.encrypted, args.cert, args.key,
                    args.database, args.jwt_secret)
    t = Thread(target=server.run, daemon=True)
    t.start()

    if args.encrypted:
        app.config['UPLOAD_FOLDER'] = args.cache_dir
        app.run(host=args.hostname, port=args.http_port,
                debug=True, use_reloader=False,
                ssl_context=(args.cert, args.key))
    else:
        app.run(host=args.hostname, port=args.http_port,
                debug=True, use_reloader=False)
