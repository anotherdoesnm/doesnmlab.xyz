# Same base as the knot service, so `knotc` here is the exact version the server
# speaks; python is added only because the API is written in it.
FROM cznic/knot:v3.6.2
RUN if command -v apk >/dev/null; then apk add --no-cache python3; \
    elif command -v apt-get >/dev/null; then apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*; fi
COPY dnsapi.py /opt/dnsapi/dnsapi.py
COPY static /opt/dnsapi/static
WORKDIR /opt/dnsapi
EXPOSE 8088
CMD ["python3", "/opt/dnsapi/dnsapi.py"]
