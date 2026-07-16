# `MetricUtils`: Logging & Telemetry

```{py:currentmodule} my.utils.MetricUtils
```

```{eval-rst}
.. autoclass:: my.utils.MetricUtils.MetricUtils
```

## `I` Logging

:::\{important}
Remote telemetry is content-denying by default: Logfire scrubbing stays enabled, argument inspection and distributed trace propagation are off, and Python log export plus per-process system metrics require explicit opt-in.
A destination comes from `LOGFIRE_TOKEN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`; without one, applications continue with local logs.
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
