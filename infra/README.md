# Voxora infrastructure

The compose stack contains the Voxora API and Next.js web client. It has no
database or RAG dependencies.

## Local containers

```bash
cp infra/.env.example infra/.env
# Set SARVAM_API_KEY, GNANI_API_KEY and the LLM settings in infra/.env
docker compose --env-file infra/.env \
  -f infra/docker/docker-compose.yml up --build
```

Open <http://localhost:3000/app>. The API is available at
<http://localhost:8000>, and its health endpoint is
<http://localhost:8000/healthz>.

Stop the stack with:

```bash
docker compose --env-file infra/.env \
  -f infra/docker/docker-compose.yml down
```

`NEXT_PUBLIC_API_URL` is baked into the web build. Use a browser-reachable URL
and rebuild the web image after changing it. For a remote deployment, set it to
the public API URL and add the web origin to `CORS_ORIGINS`.

Set `RATE_LIMIT_SECRET` to a long random value before exposing the API. Rate
limit counters are process-local, so run one API replica until they move to a
shared store. Termination between the web client and API must use TLS so
browser voice sessions use `wss://`.

Shared-platform access allows 10 queries per rolling hour per device and
caller IP. `ALLOWED_UNLIMITED` accepts a comma-separated list of IP addresses
or CIDR ranges that bypass all rate limits; leave it empty unless a trusted
operator network needs an exemption.

Provider keys are passed to the API container at runtime and are never included
in either image or the `NEXT_PUBLIC_*` browser configuration.
