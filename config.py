{% extends "base.html" %}
{% block title %}{{ employee['name'] }}{% endblock %}
{% block content %}
  <h1>Hi, {{ employee['name'] }}</h1>
  <p>
    Current status:
    {% if is_clocked_in %}
      <span class="badge in">Clocked in</span>
    {% else %}
      <span class="badge out">Clocked out</span>
    {% endif %}
  </p>
  <form method="post">
    {% if is_clocked_in %}
      <button type="submit" class="clock-out">&#10008; CLOCK OUT</button>
    {% else %}
      <button type="submit">&#10004; CLOCK IN</button>
    {% endif %}
  </form>
  <p class="muted" style="margin-top:24px;"><a href="{{ url_for('clock_home') }}">Cancel</a></p>
{% endblock %}
