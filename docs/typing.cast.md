# `cast`: The Coercion Chamber

```{py:currentmodule} my.typing.cast
```

```{eval-rst}
.. autoclass:: my.typing.cast.TypeCast
```

## `I` Registration

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.register
```

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.setup
```

## `II` Interface

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.cast
```

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.multicast
```

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.flexcast
```

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.normalize
```

```{eval-rst}
.. automethod:: my.typing.cast.TypeCast.read_scalars
```

## `III` `CastFlags`

```{eval-rst}
.. autoclass:: my.typing.cast.CastFlags
   :members:
```

## `IV` `Transform`

```{eval-rst}
.. autoclass:: my.typing.cast.Transform
```

```{eval-rst}
.. autoproperty:: my.typing.cast.Transform.ty
```

```{eval-rst}
.. autoproperty:: my.typing.cast.Transform.map_items
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.to_union
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.to_literal
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.flex_deserialize
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.concretize
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.to
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.proxy
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.by
```

```{eval-rst}
.. automethod:: my.typing.cast.Transform.__call__
```
