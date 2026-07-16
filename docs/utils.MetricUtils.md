# `MetricUtils`: Logging & Telemetry

```{py:currentmodule} my.utils.MetricUtils
```

```{eval-rst}
.. autoclass:: my.utils.MetricUtils.MetricUtils
```

## `I` Logging

:::\{important}
Remote telemetry is content-denying by default: Logfire scrubbing stays enabled, argument inspection and distributed trace propagation are off, and Python log export plus per-process system metrics require explicit opt-in.
Configuration overrides use a closed allowlist, custom or unknown scrub behavior is rejected, and environment-derived service identities must be bounded machine identifiers.
Application OTLP exporters accept local collectors (including the Podman host and an `otel-collector` sidecar) or the HTTPS `<group-id>.gitlab-o11y.com` endpoint; other destinations are rejected before providers change.
A destination comes from `LOGFIRE_TOKEN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`; without one, applications continue with local logs and retry remote setup on the next call.
Failures in optional Python-log, system-metric, or ASGI instrumentation remain local warnings and do not tear down an already-configured trace provider.
:::

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.setup_py_logging
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.setup_fire_logging
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.get_package_name
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.setup_logging
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.setup_warnings
```

## `II` Metrics

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.setup_metrics
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.measure_context
```

```{eval-rst}
.. automethod:: my.utils.MetricUtils.MetricUtils.monitor
```
