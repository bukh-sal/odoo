# Proxy-only security maintenance. Context contains the exact hash-locked APK
# closure recorded in proxy-packages.lock.json; no mutable build-time resolution.
FROM nginx:stable-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951
COPY apks/ /tmp/modular-proxy-apks/
COPY SHA256SUMS /tmp/modular-proxy-apks/SHA256SUMS
RUN cd /tmp/modular-proxy-apks \
    && sha256sum -c SHA256SUMS \
    && apk add --no-cache --no-network ./*.apk \
    && rm -rf /tmp/modular-proxy-apks
COPY proxy-packages.lock.json /opt/modular-proxy/proxy-packages.lock.json
