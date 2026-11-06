# Wyoming Soniox app image. The build context is the folder made by wyoming_soniox_app/build.sh (app files +
# package source): CI builds it for every release and publishes ghcr.io/darkdarin/wyoming-soniox (the app's
# "image"); a local app without "image:" is built by the Supervisor from the same folder.
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.14-alpine3.22
FROM ${BUILD_FROM}

# Dependencies come from uv.lock and PyPI only: the base image adds HA's own wheel index (UV_EXTRA_INDEX_URL),
# which lacks some of the locked versions.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
COPY src /tmp/src

RUN cd /tmp/src \
    && uv export --frozen --no-dev --no-emit-project --no-header -o /tmp/requirements.txt \
    && env -u UV_EXTRA_INDEX_URL uv pip install --system --break-system-packages --no-cache -r /tmp/requirements.txt \
    && env -u UV_EXTRA_INDEX_URL uv pip install --system --break-system-packages --no-cache --no-deps /tmp/src \
    && cd / && python3 -m wyoming_soniox --version \
    && rm -rf /tmp/src /tmp/requirements.txt /usr/local/bin/uv

COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
