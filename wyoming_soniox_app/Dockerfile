ARG BUILD_FROM
FROM ${BUILD_FROM}

# Supervisor passes the app version; the published app installs the package from the matching git tag.
ARG BUILD_VERSION
ARG REPO=https://github.com/darkdarin/wyoming-soniox.git

# Local builds (wyoming_soniox_app/build.sh) put the package source next to this file;
# the wildcard keeps COPY valid without it.
COPY run.sh src* /tmp/src/
RUN if [ -f /tmp/src/pyproject.toml ]; then \
        pip install --no-cache-dir /tmp/src; \
    else \
        apk add --no-cache --virtual .build-deps git \
        && pip install --no-cache-dir "wyoming-soniox @ git+${REPO}@v${BUILD_VERSION}" \
        && apk del .build-deps; \
    fi \
    && rm -rf /tmp/src

COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
