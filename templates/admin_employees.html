{% extends "base.html" %}
{% block title %}Employees{% endblock %}
{% block wrapclass %}wide{% endblock %}
{% block content %}
  <div class="nav">
    <a href="{{ url_for('admin_dashboard') }}">Dashboard</a>
    <a href="{{ url_for('admin_employees') }}">Employees</a>
    <a href="{{ url_for('clock_home') }}">Clock in/out screen</a>
    <a href="{{ url_for('admin_logout') }}">Log out</a>
  </div>

  <h1>Employees &amp; contractors</h1>
  <a class="btn" href="{{ url_for('admin_employee_new') }}">+ Add employee</a>

  <table>
    <tr><th>ID</th><th>Name</th><th>Type</th><th>Rate</th><th>Status</th><th></th></tr>
    {% for e in employees %}
    <tr>
      <td>{{ e.employee_code }}</td>
      <td>{{ e.name }}</td>
      <td>{{ e.worker_type|capitalize }}</td>
      <td>${{ "%.2f"|format(e.hourly_rate) }}/hr</td>
      <td>{% if e.active %}Active{% else %}Inactive{% endif %}</td>
      <td><a href="{{ url_for('admin_employee_edit', emp_id=e.id) }}">Edit</a></td>
    </tr>
    {% else %}
    <tr><td colspan="6" class="muted">No employees yet.</td></tr>
    {% endfor %}
  </table>
{% endblock %}
