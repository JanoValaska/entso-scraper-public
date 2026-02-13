output "rule_arns" {
  description = "ARNs of the EventBridge rules"
  value = {
    day_ahead_prices_cz    = aws_cloudwatch_event_rule.day_ahead_prices_cz.arn
    actual_load_de         = aws_cloudwatch_event_rule.actual_load_de.arn
    generation_forecast_at = aws_cloudwatch_event_rule.generation_forecast_at.arn
  }
}

output "rule_names" {
  description = "Names of the EventBridge rules"
  value = {
    day_ahead_prices_cz    = aws_cloudwatch_event_rule.day_ahead_prices_cz.name
    actual_load_de         = aws_cloudwatch_event_rule.actual_load_de.name
    generation_forecast_at = aws_cloudwatch_event_rule.generation_forecast_at.name
  }
}