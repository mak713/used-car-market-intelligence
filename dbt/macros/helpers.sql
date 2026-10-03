{# Source text -> trimmed text; empty strings and premium/redacted placeholders become NULL. #}
{% macro clean_text(expr) -%}
    nullif(nullif(btrim({{ expr }}), ''), '[PREMIUM]')
{%- endmacro %}

{# Typed extractors from the raw JSONB payload. #}
{% macro j_text(key) -%}{{ clean_text("payload ->> '" ~ key ~ "'") }}{%- endmacro %}
{% macro j_int(key) -%}(({{ clean_text("payload ->> '" ~ key ~ "'") }})::numeric)::integer{%- endmacro %}
{% macro j_bigint(key) -%}(({{ clean_text("payload ->> '" ~ key ~ "'") }})::numeric)::bigint{%- endmacro %}
{% macro j_num(key) -%}({{ clean_text("payload ->> '" ~ key ~ "'") }})::numeric{%- endmacro %}
{% macro j_bool(key) -%}({{ clean_text("payload ->> '" ~ key ~ "'") }})::boolean{%- endmacro %}

{# Deterministic surrogate key: md5 over |-joined, NULL-safe parts. #}
{% macro surrogate_key(parts) -%}
    md5({% for p in parts %}coalesce(({{ p }})::text, '~null~'){% if not loop.last %} || '|' || {% endif %}{% endfor %})
{%- endmacro %}
