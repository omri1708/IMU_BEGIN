package policy.contracts

# Example business invariant: refund only within 30 days & amount <= order.total
violation[msg] {
  input.event.type == "refund.create"
  input.event.days_since_order > 30
  msg := "refund window exceeded"
}

violation[msg] {
  input.event.type == "refund.create"
  input.event.amount > input.event.order_total
  msg := "refund exceeds order total"
}
