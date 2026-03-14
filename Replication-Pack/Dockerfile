FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    bash \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /pack

COPY . /pack/

RUN chmod +x VERIFY/verify.sh

ENTRYPOINT ["bash"]