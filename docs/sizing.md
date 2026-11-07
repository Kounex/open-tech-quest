# Sizing an event

Size for simultaneously active participants. Our room/standings mix generated
about **0.45 API requests/s per person**, including polling without submissions.
Challenge workloads ran on separate clusters. Closed pages do not generate this
polling load.

## What we measured

In November 2026, plugin **0.1.18 / CTFd 3.8.9** was tested on multi-node OpenShift
with 16-vCPU AMD EPYC VM nodes. The disposable instance had 50 teams of eight,
25 challenges and up to 1,070 historical solves before the final flag burst.
Authenticated protocol clients used native sessions, CSRF and the shipped
polling scheduler through the public HTTPS Route. This was not 400 rendered
browsers.

We captured request latency/errors, CPU/throttling, memory, traffic, database
connections/lock waits and restarts. The selected profile used one CTFd pod,
12 Gunicorn worker processes, an 8-CPU request and a 10-CPU limit:

- **400 clients for ten minutes:** 109,089 requests, zero unrecovered errors,
  about 6 application CPU cores and steady endpoint p95 up to 0.37s.
- **50 simultaneous team flags:** all succeeded, p95 7.9s; all 400 teammates
  observed the result. The shared event write lock still serializes submissions.
- **400 reconnects and 400 reloads, each over ten seconds:** all completed.
  Four stale-connection GETs recovered with one retry each; POSTs were not retried.

An 8-CPU limit exceeded the two-second steady endpoint-p95 target, so the
10-CPU limit was retained. In-cluster cold downloads passed, but external
connection stress exposed socket closures and deadlines despite spare CPU.
These results qualify the measured origin workload, not venue Wi-Fi/WAN or
end-to-end browser readiness.

## Starting estimates: 50–500 attendees

Assume the same polling mix and roughly eight attendees per team. **Only the
400-attendee row is measured.** Other rows scale its CPU allocation, rounding
up to half a core; hardware, history, team count and submission bursts can change
requirements.

| Active attendees | Approx. API requests/s | CTFd CPU request / limit |
|---:|---:|---:|
| 50 | 23 | 1 / 1.5 cores |
| 100 | 45 | 2 / 2.5 cores |
| 150 | 68 | 3 / 4 cores |
| 200 | 90 | 4 / 5 cores |
| 250 | 113 | 5 / 6.5 cores |
| 300 | 135 | 6 / 7.5 cores |
| 350 | 158 | 7 / 9 cores |
| **400 (measured)** | **180–182** | **8 / 10 cores** |
| 450 | 203 | 9 / 11.5 cores |
| 500 | 225 | 10 / 12.5 cores |

All rows retain **12 workers and CTFd memory requests/limits of 2 / 4 GiB**;
smaller worker/memory profiles were not benchmarked. Add the same supporting
services to each row:

| Component | CPU request / limit | Memory request / limit |
|---|---|---|
| MariaDB | 1 / 2 cores | 1 / 2 GiB |
| Redis | 250m / 500m | 128 / 256 MiB |

Workers are processes, independent of the CPU limit. With a pool size of ten and
zero overflow per worker, twelve workers allow at most 120 application database
connections. Leave capacity for administration and migrations; recheck the DB
connection budget when changing workers. More CPU does not remove the flag-write
lock. Attendance above 400 needs additional load testing, including larger team
bursts.

## OpenShift example: 400 attendees

Apply this **strategic merge patch to an existing CTFd Deployment**, adjusting
its namespace and container name. Reference it from your Kustomization's
`patches` list. It sets the application allocation, not a complete installation;
provide the image, database, cache, secrets, storage, Service and Route separately.
Use the MariaDB and Redis resources above.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ctfd
  namespace: ctfd
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: ctfd
          env:
            - name: WORKERS
              value: "12"
            - name: SQLALCHEMY_MAX_OVERFLOW
              value: "0"
          resources:
            requests:
              cpu: "8"
              memory: 2Gi
            limits:
              cpu: "10"
              memory: 4Gi
```

The stack totals **9.25 requested / 12.5 limited CPU** and **3.125 / 6.25 GiB
memory**, excluding OpenShift. The CTFd pod needs a node with room for its full
8-CPU / 2-GiB request; CPU limits do not reserve capacity. Test storage requests
were 10 GiB for uploads/logs, 10 GiB for MariaDB and 1 GiB for Redis; adjust for
your content and retention.

Before an event, repeat steady polling, simultaneous flags, reconnects and cold
loads with representative history. Inspect tail latency and errors alongside
CPU, memory, traffic and DB lock waits. Use a disposable instance and validate
from the venue network as well as inside the cluster.
