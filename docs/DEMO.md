# Local demo without AI charges

The demo runs a disposable Cardchemy installation with an authored two-card
biology example. It uses the real API, PostgreSQL, PDF extraction, generation
pipeline, email worker, instructor review, enrollment and study persistence.
The generation worker receives a private deterministic test provider that has
no provider SDK or network client. It does not call Gemini or an OpenAI endpoint.

Install the development dependencies in [local setup](development/LOCAL-SETUP.md),
start Docker, and install Chromium once with `npx playwright install chromium`
from `frontend`. Use the backend development environment's Python from the
repository root:

```text
python scripts/test_journey.py --demo --demo-minutes 30
```

For a packaged frontend candidate, build the Nginx image locally (or use the
already-built candidate's local reference), then select it explicitly:

```text
docker build -t cardchemy-frontend:demo ./frontend
python scripts/test_journey.py --demo --demo-minutes 30 --demo-frontend-image cardchemy-frontend:demo
```

Image mode requires the image to exist locally and runs its pinned image ID with
pulling disabled. It verifies that the packaged Nginx configuration matches this
checkout. It copies only a private non-secret configuration file into the
temporary container before starting Nginx, changing only the upstream server from
`backend:8000` to `host.docker.internal:<generated API port>`; security headers,
static assets, cookie rewriting and safe logging remain packaged behavior.
The copy preserves the configuration's root ownership and `0644` file mode;
the generated credential directory is never mounted or copied into the container.
The Nginx container binds a Docker-assigned random loopback host port and uses a
uniquely named disposable network for the packaged Docker DNS resolver. The host API
also remains on `127.0.0.1`. This mode requires Docker Desktop or another Docker
environment where `host.docker.internal` reaches a host loopback listener. If
the packaged frontend cannot reach that listener, the harness stops and cleans
up; it does not widen the API binding or change the host's networking.

The default demo first builds the frontend into private temporary storage; image
mode serves the frontend build already in the selected image. Both run the
real instructor/student browser journey and verify its database records.
After that succeeds it prints a loopback application URL and the path to a
private `demo-sign-in.json` file. Open that file locally to obtain the generated
instructor and student sign-in details. Keep the file private; do not paste its
contents into an issue, chat, screenshot or release evidence. No password is
printed by the harness.

Sign in as the instructor to explore **Journey Biology**, review the approved
**Journey Leaf Facts** set, preview cards and inspect its publication state.
Sign out and use the student account to open the enrolled course and select
**Review Again**. The scripted journey already answered both cards; completion
is 100%, while mastery remains 0% after the first attempt. Review Again enables
another study session immediately. Both accounts can exercise normal account
recovery; the generated email remains in disposable loopback Mailpit, whose
URL is in the private sign-in file.

The fixture PDF is `leaf-facts.pdf` beside the sign-in file. To repeat generation,
upload that PDF and request exactly two cards. The deterministic provider only
supports those authored chlorophyll/photosynthesis facts. Other PDFs, larger
requests or real model quality are outside this demonstration.

The interactive period defaults to 15 minutes and is limited to 1–60 minutes.
Press Ctrl+C in the original terminal to finish earlier. The command terminates
its processes, removes its uniquely named containers and temporary data, and
deletes the generated credentials and any temporary frontend build. Image mode
also removes its uniquely named Nginx container and network, while keeping the selected
local image. It uses random loopback
ports, no persistent volumes, and injected process settings that ignore the
operator's root `.env` and application environment. It never modifies an
existing installation or regenerates its secrets. Do not expose the demo to a
public network or use it for real documents or users.

For a noninteractive regression/demo run use `python scripts/test_journey.py`;
its normal behavior exits immediately after verification. See
[testing](TESTING.md) for the exact proof and [accessibility](ACCESSIBILITY.md)
for the separate manual spoken-output release checks. The default temporary
frontend uses a production JavaScript build served by Vite preview with the
guarded same-origin API proxy. Select the packaged-image mode for those checks
when validating the Nginx candidate. Automated journey success does not verify
spoken output, a production deployment or the signatures of a published release.
