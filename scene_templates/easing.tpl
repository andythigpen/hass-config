{#
    Easing functions from https://easings.net/ and http://robertpenner.com/easing/
    t: current time
    b: beginning value
    c: change in value
    d: duration
#}

{% macro in_quad(t, b, c, d) -%}
  {%- set t = t / d -%}
  {{- (c * (t ** 2) + b) -}}
{%- endmacro %}

{% macro in_out_quad(t, b, c, d) -%}
  {%- set t = t / d * 2 -%}
  {%- if t < 1 -%}
    {{- (c / 2 * t * t + b) -}}
  {%- else -%}
    {{- (-c / 2 * ((t - 1) * (t - 3) - 1) + b) -}}
  {%- endif -%}
{%- endmacro %}

{% macro out_quad(t, b, c, d) -%}
  {%- set t = t / d -%}
  {{- (-c * t * (t - 2) + b) -}}
{%- endmacro %}
