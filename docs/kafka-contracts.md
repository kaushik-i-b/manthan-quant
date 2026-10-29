# Kafka contracts

No Kafka message was read from the participant portal. This machine could not open `192.168.65.157:9094` on 29 October 2026. See `docs/api-discovery-report.md`.

| Item | Value | Status |
| --- | --- | --- |
| Broker | `192.168.65.157:9094` | INFERRED from the build brief, not confirmed on the broker |
| Topics | `market.ticks`, `market.news` | INFERRED from the build brief |
| Authentication | | MISSING |
| Consumer group | | MISSING. The engine will not start a consumer while `KAFKA_GROUP_ID` is empty |
| Partitions | | MISSING |
| Encoding | | MISSING |
| Tick schema | | MISSING |
| News schema | | MISSING |
| Ordering and offsets | | MISSING |

The internal schemas `manthan-quant.internal.tick.v1` and `manthan-quant.internal.news.v1` are for the local mock tape only. They are not competition messages.

`parse_topic_message` accepts a topic only when a portal catalog marks that topic `verified` and maps the candle fields. A partial map is rejected. Inferred fields are not traded.
