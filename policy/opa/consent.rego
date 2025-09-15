package policy.consent

default granted = false

# consent must exist for sensitive processing
granted {
  not input.resource.sensitive
}

granted {
  input.resource.sensitive
  input.request.user.consent[input.resource.purpose]
}
