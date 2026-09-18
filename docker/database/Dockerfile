FROM postgres:16-alpine3.24@sha256:3c5c8892d184f738f4fe282d14ddaa613a38f00f4189d2d94725ebe6f2909ddb AS vector-build
RUN apk add --no-cache \
    jansson=2.15.0-r0 binutils=2.45.1-r1 libgcc-static=15.2.0-r5 \
    libgomp=15.2.0-r5 libatomic=15.2.0-r5 gmp=6.3.0-r4 isl26=0.26-r2 \
    mpfr4=4.2.2-r0 mpc1=1.3.1-r1 gcc=15.2.0-r5 make=4.4.1-r4 musl-dev=1.2.6-r2
RUN wget -q -O /tmp/pgvector.tar.gz https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.6 \
    && echo "10bf9938906e5d643bbc4a7eea104b6f57ba4898e5b76b20e60484ea1d5a7f8f  /tmp/pgvector.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/pgvector.tar.gz -C /tmp \
    && make -C /tmp/pgvector-0.8.6 OPTFLAGS="" with_llvm=no \
    && make -C /tmp/pgvector-0.8.6 OPTFLAGS="" with_llvm=no DESTDIR=/out install \
    && mkdir -p /out/usr/local/share/doc/pgvector \
    && cp /tmp/pgvector-0.8.6/LICENSE /out/usr/local/share/doc/pgvector/LICENSE
FROM postgres:16-alpine3.24@sha256:3c5c8892d184f738f4fe282d14ddaa613a38f00f4189d2d94725ebe6f2909ddb AS sanitized-runtime
ENV POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale-provider=icu --icu-locale=en-US"
RUN apk add --no-cache su-exec=0.3-r0 \
    && rm /usr/local/bin/gosu /usr/local/bin/su-exec \
    && ln -s /sbin/su-exec /usr/local/bin/gosu \
    && ln -s /sbin/su-exec /usr/local/bin/su-exec \
    && gosu postgres test "$(id -u postgres)" = "70"
COPY --from=vector-build /out/usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=vector-build /out/usr/local/share/postgresql/extension/ /usr/local/share/postgresql/extension/
COPY --from=vector-build /out/usr/local/share/doc/pgvector/LICENSE /usr/local/share/doc/pgvector/LICENSE
FROM scratch
COPY --from=sanitized-runtime / /
COPY --chmod=755 database-entrypoint.sh /usr/local/bin/cardchemy-database-entrypoint.sh
COPY --chmod=755 verify-initial-profile.sh /docker-entrypoint-initdb.d/00-cardchemy-verify-profile.sh
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=en_US.utf8 PG_MAJOR=16 PG_VERSION=16.15 PGDATA=/var/lib/postgresql/data \
    POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale-provider=icu --icu-locale=en-US"
VOLUME /var/lib/postgresql/data
EXPOSE 5432
STOPSIGNAL SIGINT
ENTRYPOINT ["cardchemy-database-entrypoint.sh"]
CMD ["postgres"]
