FROM flink:1.18-scala_2.12-java11

# S3 플러그인 설치
RUN mkdir -p /opt/flink/plugins/s3-fs-hadoop && \
    wget -q -P /opt/flink/plugins/s3-fs-hadoop/ \
    https://repo1.maven.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.18.1/flink-s3-fs-hadoop-1.18.1.jar

# Paimon, Kafka 커넥터 설치
RUN wget -q -P /opt/flink/lib/ \
    https://repo1.maven.org/maven2/org/apache/paimon/paimon-flink-1.18/0.7.0-incubating/paimon-flink-1.18-0.7.0-incubating.jar && \
    wget -q -P /opt/flink/lib/ \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar && \
    wget -q -P /opt/flink/lib/ \
    https://repo1.maven.org/maven2/org/apache/paimon/paimon-s3/0.7.0-incubating/paimon-s3-0.7.0-incubating.jar && \
    wget -q -P /opt/flink/lib/ \
    https://repo1.maven.org/maven2/org/apache/flink/flink-shaded-hadoop-2-uber/2.8.3-10.0/flink-shaded-hadoop-2-uber-2.8.3-10.0.jar

# 프로덕션 설정 복사 (선택적)
COPY flink-conf.yaml /opt/flink/conf/flink-conf-production.yaml
