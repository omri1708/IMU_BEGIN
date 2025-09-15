package policy.abac

default allow = false

allow {
  input.request.user.role == "admin"
}

allow {
  input.request.user.role == "manager"
  input.request.action == "read"
}

# example fine-grain: only creator can edit resource
allow {
  input.request.action == "update"
  input.resource.owner == input.request.user.id
}
