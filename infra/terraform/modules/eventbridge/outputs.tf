output "schedule_arns" {
  description = "ARNs of the EventBridge Scheduler schedules"
  value = {
    day_ahead_prices_cz    = aws_scheduler_schedule.day_ahead_prices_cz.arn
    actual_load_de         = aws_scheduler_schedule.actual_load_de.arn
    generation_forecast_at = aws_scheduler_schedule.generation_forecast_at.arn
  }
}

output "schedule_names" {
  description = "Names of the EventBridge Scheduler schedules"
  value = {
    day_ahead_prices_cz    = aws_scheduler_schedule.day_ahead_prices_cz.name
    actual_load_de         = aws_scheduler_schedule.actual_load_de.name
    generation_forecast_at = aws_scheduler_schedule.generation_forecast_at.name
  }
}