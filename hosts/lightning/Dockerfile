# Built from the binary compiled on nexus: the VPS has no memory to spare for a Go
# toolchain, and upstream's containerfile would run one inside the build.
FROM scratch
USER 1001:1001
COPY lightning /lightning
COPY ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
VOLUME ["/data"]
WORKDIR /data
ENTRYPOINT ["/lightning"]
