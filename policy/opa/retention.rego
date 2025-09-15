package policy.retention

default within = false

within {
  not input.resource.retention_days
}

within {
  now := time.now_ns() / 1000000000
  created := input.resource.created_at
  limit := input.resource.retention_days * 24 * 3600
  now - created <= limit
}
