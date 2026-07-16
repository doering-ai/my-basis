############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from typing import Any, cast

### EXTERNAL
import pytest as pyt
import jinja2 as jn
import pydantic as pyd

### INTERNAL
from myBasis.types.Template import Template


############
### BODY ###
############
class TestTemplateConstruction:
    """Tests for Template construction via ``get()``."""

    def test_get_raw(self):
        t = Template.get(raw='Hello {{ name }}')
        assert isinstance(t, Template)
        assert isinstance(t.root, jn.Template)

    def test_get_raw_renders(self):
        t = Template.get(raw='Hello {{ name }}')
        assert t.root.render(name='World') == 'Hello World'

    def test_get_requires_path_or_raw(self):
        with pyt.raises(ValueError, match='path or raw'):
            cast('Any', Template.get)()

    def test_get_raw_caches(self):
        """``_new_from_raw`` uses ``lru_cache``."""
        t1 = Template._new_from_raw('cached {{ x }}')
        t2 = Template._new_from_raw('cached {{ x }}')
        assert t1 is t2

    def test_is_root_model(self):
        assert issubclass(Template, pyd.RootModel)

    def test_root_field(self):
        t = Template.get(raw='test')
        assert hasattr(t, 'root')

    def test_template_with_trim_blocks(self):
        """Default environment has trim_blocks=True."""
        raw = '{% if True %}\n  Hello\n{% endif %}'
        t = Template.get(raw=raw)
        result = t.root.render()
        # With trim_blocks, the newline after {% endif %} is trimmed
        assert 'Hello' in result


class TestTemplateEnvironments:
    """Tests for Template environment management."""

    def test_default_env_exists(self):
        assert '' in Template.ENVS

    def test_default_env_has_defaults(self):
        env = Template.ENVS['']
        assert env.trim_blocks is True
        assert env.lstrip_blocks is True

    def test_defaults_class_var(self):
        assert Template.DEFAULTS['trim_blocks'] is True
        assert Template.DEFAULTS['lstrip_blocks'] is True


class TestTemplateInferRoot:
    """Tests for ``_infer_root``."""

    def test_finds_templates_dir(self, tmp_path: Path):
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        template_file = templates_dir / 'test.j2'
        template_file.touch()
        result = Template._infer_root(template_file)
        assert result == templates_dir

    def test_finds_data_dir(self, tmp_path: Path):
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        template_file = data_dir / 'test.j2'
        template_file.touch()
        result = Template._infer_root(template_file)
        assert result == data_dir

    def test_defaults_to_parent(self, tmp_path: Path):
        template_file = tmp_path / 'test.j2'
        template_file.touch()
        result = Template._infer_root(template_file)
        assert result == tmp_path

    def test_finds_assets_dir(self, tmp_path: Path):
        assets_dir = tmp_path / 'assets'
        assets_dir.mkdir()
        template_file = assets_dir / 'test.j2'
        template_file.touch()
        result = Template._infer_root(template_file)
        assert result == assets_dir

    def test_nested_templates_dir(self, tmp_path: Path):
        templates_dir = tmp_path / 'resources' / 'templates'
        templates_dir.mkdir(parents=True)
        template_file = templates_dir / 'deep.j2'
        template_file.touch()
        result = Template._infer_root(template_file)
        assert result == templates_dir


class TestTemplateGetFromPath:
    """Tests for ``get(path=...)``."""

    def test_get_from_path(self, tmp_path: Path):
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        template_file = templates_dir / 'hello.j2'
        template_file.write_text('Hello {{ name }}!')

        t = Template.get(template_file)
        assert isinstance(t, Template)
        assert t.root.render(name='World') == 'Hello World!'

    def test_get_from_path_caches(self, tmp_path: Path):
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        template_file = templates_dir / 'cached.j2'
        template_file.write_text('cached {{ x }}')

        t1 = Template._new_from_path(str(template_file))
        t2 = Template._new_from_path(str(template_file))
        assert t1 is t2

    def test_get_from_path_creates_env(self, tmp_path: Path):
        templates_dir = tmp_path / 'templates'
        templates_dir.mkdir()
        template_file = templates_dir / 'env_test.j2'
        template_file.write_text('test')

        Template.get(template_file)
        # The environment for this template root should now be cached
        assert str(templates_dir) in Template.ENVS


class TestTemplateRegex:
    """Tests for the ``RGXS`` class variable."""

    def test_has_dirname_pattern(self):
        assert 'dirname' in Template.RGXS

    def test_dirname_matches_templates(self):
        pat = Template.RGXS['dirname']
        assert pat.fullmatch('templates')
        assert pat.fullmatch('tmpl')
        assert pat.fullmatch('data')
        assert pat.fullmatch('assets')
        assert pat.fullmatch('resources')

    def test_dirname_no_match_random(self):
        pat = Template.RGXS['dirname']
        assert not pat.fullmatch('src')
        assert not pat.fullmatch('random')
