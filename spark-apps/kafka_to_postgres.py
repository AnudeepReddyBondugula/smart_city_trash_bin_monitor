from pyspark.sql import SparkSession  # type: ignore
from pyspark.sql.functions import (  # type: ignore
    from_json,
    col,
    window,
    avg,
    max,
    min,
    approx_count_distinct,
    when,
    sum as spark_sum,
    lit,
    current_timestamp
)
from pyspark.sql.types import (  # type: ignore
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
    TimestampType
)
from pyspark.sql.streaming import StreamingQueryListener  # type: ignore
import time
import psycopg2
from psycopg2.extras import execute_batch
from psycopg2 import OperationalError
from config import Config


# ----------------------------------------------------
# Query progress logger
# ----------------------------------------------------
class QueryProgressLogger(StreamingQueryListener):
    def onQueryStarted(self, event):
        try:
            print(f"🚀 Query started | name={event.name}", flush=True)
        except Exception:
            pass

    def onQueryProgress(self, event):
        try:
            p = event.progress
            duration = p.durationMs or {}

            # Log ONLY minimal safe fields
            print(
                f"📊 Batch {p.batchId} | "
                f"rows={p.numInputRows} | "
                f"addBatch={duration.get('addBatch', 'NA')}ms | "
                f"trigger={duration.get('triggerExecution', 'NA')}ms",
                flush=True
            )
        except Exception:
            # ABSOLUTELY NEVER crash listener
            pass

    def onQueryIdle(self, event):
        pass

    def onQueryTerminated(self, event):
        try:
            print(f"🛑 Query terminated | exception={event.exception}", flush=True)
        except Exception:
            pass



# ----------------------------------------------------
# Main Streaming Job
# ----------------------------------------------------
class WardFillLevelStreamingJob:

    def __init__(self):
        self.spark = self._create_spark_session()
        self.schema = self._define_schema()
        self.avg_checkpoint = "/opt/spark-checkpoints/ward_fill_level_avg_v1"
        self.risk_checkpoint = "/opt/spark-checkpoints/ward_fill_level_risk_v1"
        self.dlq_checkpoint = "/opt/spark-checkpoints/dlq_invalid"

    # ------------------------------------------------
    # Spark Session
    # ------------------------------------------------
    def _create_spark_session(self) -> SparkSession:
        spark = (
            SparkSession.builder
            .appName("WardFillLevelAggregation")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.default.parallelism", "2")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")
        print("🚀 Spark session initialized")
        return spark

    # ------------------------------------------------
    # Schema
    # ------------------------------------------------
    def _define_schema(self) -> StructType:
        return StructType([
            StructField("schema_version", IntegerType(), True),
            StructField("bin_id", StringType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("ward", IntegerType(), True),
            StructField("fill_level", IntegerType(), True),
            StructField("temperature", DoubleType(), True),
            StructField("humidity", IntegerType(), True),
            StructField("timestamp", TimestampType(), True),
        ])

    # ------------------------------------------------
    # Kafka Source
    # ------------------------------------------------
    def read_from_kafka(self):
        print("📡 Connecting to Kafka")
        return (
            self.spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", Config.KAFKA_BOOTSTRAP)
            .option("subscribe", Config.VALID_TOPIC)
            .option("startingOffsets", "latest")
            .option("maxOffsetsPerTrigger", 500)
            .option("failOnDataLoss", "false")
            .load()
        )

    # ------------------------------------------------
    # Parse with DLQ
    # ------------------------------------------------
    def parse_with_dlq(self, kafka_df):
        raw_df = kafka_df.select(
            col("value").cast("string").alias("raw_value"),
            col("topic"),
            col("partition"),
            col("offset")
        )

        parsed_df = raw_df.withColumn(
            "data",
            from_json(col("raw_value"), self.schema)
        )

        valid_df = (
            parsed_df
            .filter(col("data").isNotNull())
            .select("data.*")
            .filter(col("timestamp").isNotNull())
            .withWatermark("timestamp", "2 minutes")
            .dropDuplicates(["bin_id", "timestamp"])
        )

        invalid_df = (
            parsed_df
            .filter(col("data").isNull())
            .withColumn("error_reason", lit("JSON_PARSE_FAILED"))
            .withColumn("error_time", current_timestamp())
        )

        return valid_df, invalid_df

    # ------------------------------------------------
    # DLQ Writer
    # ------------------------------------------------
    def start_dlq_stream(self, invalid_df):
        (
            invalid_df
            .selectExpr("to_json(struct(*)) AS value")
            .writeStream
            .format("kafka")
            .option("kafka.bootstrap.servers", Config.KAFKA_BOOTSTRAP)
            .option("topic", Config.INVALID_TOPIC)
            .option("checkpointLocation", self.dlq_checkpoint)
            .start()
        )

    # ------------------------------------------------
    # Aggregations
    # ------------------------------------------------
    def aggregate_avg(self, df):
        return (
            df.groupBy(
                window(col("timestamp"), "1 minute"),
                col("ward")
            )
            .agg(avg("fill_level").alias("avg_fill_level"))
            .select(
                col("ward"),
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("avg_fill_level")
            )
        )

    def aggregate_risk(self, df):
        return (
            df.groupBy(
                window(col("timestamp"), "1 minute"),
                col("ward")
            )
            .agg(
                avg("fill_level").alias("avg_fill_level"),
                max("fill_level").alias("max_fill_level"),
                min("fill_level").alias("min_fill_level"),
                spark_sum(
                    when(col("fill_level") >= 80, 1).otherwise(0)
                ).alias("bins_above_80")
            )
            .select(
                col("ward"),
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("avg_fill_level"),
                col("max_fill_level"),
                col("min_fill_level"),
                col("bins_above_80")
            )
        )


    # ------------------------------------------------
    # DB Retry Helper
    # ------------------------------------------------
    @staticmethod
    def with_db_retry(fn, retries=3, backoff=2):
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except OperationalError:
                if attempt == retries:
                    raise
                sleep = backoff ** attempt
                print(f"⚠️ DB error, retrying in {sleep}s")
                time.sleep(sleep)

    # ------------------------------------------------
    # Safe foreachBatch wrapper
    # ------------------------------------------------
    @staticmethod
    def safe_foreach_batch(fn):
        def wrapper(df, batch_id):
            try:
                fn(df, batch_id)
            except Exception as e:
                print(f"🔥 Batch {batch_id} failed: {e}")
                raise
        return wrapper

    # ------------------------------------------------
    # PostgreSQL Writers
    # ------------------------------------------------
    @staticmethod
    def write_avg_to_postgres(batch_df, batch_id):
        pdf = batch_df.toPandas()
        if pdf.empty:
            return

        rows = list(
            zip(
                pdf["ward"],
                pdf["window_start"],
                pdf["window_end"],
                pdf["avg_fill_level"]
            )
        )

        def db_write():
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            sql = """
                INSERT INTO ward_fill_level_agg
                (ward, window_start, window_end, avg_fill_level)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (ward, window_start, window_end)
                DO UPDATE SET avg_fill_level = EXCLUDED.avg_fill_level;
            """
            with conn:
                with conn.cursor() as cur:
                    execute_batch(cur, sql, rows, page_size=500)
            conn.close()

        WardFillLevelStreamingJob.with_db_retry(db_write)
        print(f"✅ Avg batch {batch_id} committed | rows={len(rows)}")

    @staticmethod
    def write_risk_to_postgres(batch_df, batch_id):
        pdf = batch_df.toPandas()
        if pdf.empty:
            return

        rows = list(
            zip(
                pdf["ward"],
                pdf["window_start"],
                pdf["window_end"],
                pdf["avg_fill_level"],
                pdf["max_fill_level"],
                pdf["min_fill_level"],
                pdf["bins_above_80"],
            )
        )

        def db_write():
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            sql = """
                INSERT INTO ward_fill_level_risk_agg (
                    ward, window_start, window_end,
                    avg_fill_level, max_fill_level, min_fill_level, bins_above_80
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ward, window_start, window_end)
                DO UPDATE SET
                    avg_fill_level = EXCLUDED.avg_fill_level,
                    max_fill_level = EXCLUDED.max_fill_level,
                    min_fill_level = EXCLUDED.min_fill_level,
                    bins_above_80 = EXCLUDED.bins_above_80
            """
            with conn:
                with conn.cursor() as cur:
                    execute_batch(cur, sql, rows, page_size=500)
            conn.close()

        WardFillLevelStreamingJob.with_db_retry(db_write)
        print(f"✅ Risk batch {batch_id} committed | rows={len(rows)}")

    # ------------------------------------------------
    # Start Streaming
    # ------------------------------------------------
    def start(self):
        kafka_df = self.read_from_kafka()
        valid_df, invalid_df = self.parse_with_dlq(kafka_df)

        self.start_dlq_stream(invalid_df)
        self.spark.streams.addListener(QueryProgressLogger())

        avg_df = self.aggregate_avg(valid_df)
        risk_df = self.aggregate_risk(valid_df)

        avg_df.writeStream \
            .queryName("ward_fill_level_avg") \
            .trigger(processingTime=Config.TRIGGER_INTERVAL) \
            .outputMode("update") \
            .foreachBatch(self.safe_foreach_batch(self.write_avg_to_postgres)) \
            .option("checkpointLocation", self.avg_checkpoint) \
            .start()

        risk_df.writeStream \
            .queryName("ward_fill_level_risk") \
            .trigger(processingTime=Config.TRIGGER_INTERVAL) \
            .outputMode("update") \
            .foreachBatch(self.safe_foreach_batch(self.write_risk_to_postgres)) \
            .option("checkpointLocation", self.risk_checkpoint) \
            .start()

        print("🚀 Both Spark streaming queries started")
        self.spark.streams.awaitAnyTermination()


# ----------------------------------------------------
# Entry point
# ----------------------------------------------------
if __name__ == "__main__":
    WardFillLevelStreamingJob().start()
