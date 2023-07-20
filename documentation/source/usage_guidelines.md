# Usage

Each user and device client is a separate process.

## Prerequisites
Server and user client require `python3`. \
Device client building and schema generation requires `rust` toolchain. \
For certificate generation you can use `openssl`.

## Server
### Building

Run `python3 -m build` in `server` directory

### Installing

Run `pip3 install .` in `server` directory

### Running

Ensure that `json_schemas` directory is available.

`python3 -m rdfm_mgmt_server`

## Device client
### Building

```
cd device
cargo build
```

Compiled client can be found at: `device/target/debug/rdfm_mgmt_device`

To build device schemas run use `rdfm_schema_generator`

### Running

Register a device:

- using binary

```
./rdfm_mgmt_device --name "devicename"
```

- using `cargo` (inside `device` directory):

```
cargo run --bin rdfm_mgmt_device -- --name "devicename"
```

to include metadata provide file in argument `--file-metadata`

Client names should not contain whitespaces.

## User client
### Building

Run `python3 -m build` in `client` directory

### Installing

Run `pip3 install .` in `client` directory

### Running

Ensure that `json_schemas` directory is available.

Register a user:

```
python3 -m rdfm_mgmt_client username
```

## Encrypting communication

To use encrypted communication between all parties generate certificates. \
To generate samples you can use `certgen.sh` script available
for testing purposes.

You can turn off encrypted communication with server and client
by using `no_ssl` argument.

## Using a connected client

List connected devices:

```
LIST
```

Fetch information about device:

```
REQ device_name info
```

Requesting device to upload new metadata:

```
REQ device_name update
```

Request **proxy** connection with a device:

```
REQ device_name proxy
```

**File transfer**:

Upload file to device:

```
REQ device_name upload file_path src_file_path
```

Where file_path indicates path on device, src_file_path indicates of file
to upload.

Download file from device:

```
REQ device_name download file_path
```

**Connecting to the device**:

If proxy request was succesful, a message with port to connect to will be sent
to the user. \
To connect just use these (or similiar) programs:

**Encrypted:**

```openssl s_client -CAfile certs/CA.crt -quiet -connect SERVER_ADDR:PORT```

**Not encrypted:**

```nc SERVER_ADDR PORT```

Exit client:

```
exit
```

## Communicating with server via HTTP (server management)

To use encrypted connection via HTTP request matching `CA.crt` certificate
is needed.

Endpoints:

GET `/`

Returns list connected devices

GET `/device/<devicename>`

Fetch information about device

GET `/device/<devicename>/update`

Request device to upload new metadata

GET `/device/<devicename>/proxy`

Request **proxy** connection with a device