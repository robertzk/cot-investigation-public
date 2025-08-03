Necessary SSH tunnels to establish when running the stack remotely:

```
ssh -L 8002:localhost:8001 paperspace@<IP> # Forward backend port to local machine
ssh -L 5434:localhost:5433 paperspace@184.105.3.208 # Forward postgres port to local machine
```

Make sure in the remote .env file that the `DATABASE_URL` is set:

```
# Route backend's DB connection through local network, as Paperspace docker seems to have networking issues between containers.
export DATABASE_URL=postgresql://chainofthought:chainofthought@host.docker.internal:5433/chainofthought
```
