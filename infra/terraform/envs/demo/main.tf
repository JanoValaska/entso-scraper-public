module "vpc" {
  source      = "../../modules/vpc"
  project     = local.project
  environment = var.environment
}

module "nat" {
  source             = "../../modules/nat"
  vpc_id             = module.vpc.vpc_id
  public_subnet_id   = module.vpc.public_subnet_ids[0]
  private_subnet_ids = module.vpc.private_subnet_ids
  instance_type      = "t3.micro"
  project            = local.project
  environment        = var.environment
}

module "s3_data" {
  source      = "../../modules/s3"
  bucket_name = var.data_bucket_name
  project     = local.project
  environment = var.environment
}

module "lambda" {
  source             = "../../modules/lambda"
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  data_bucket_arn    = module.s3_data.bucket_arn
  data_bucket_id     = module.s3_data.bucket_id
  project            = local.project
  environment        = var.environment

  environment_variables = {
    ENVIRONMENT = var.environment
  }
}

module "eventbridge" {
  source               = "../../modules/eventbridge"
  project              = local.project
  environment          = var.environment
  lambda_function_arn  = module.lambda.lambda_function_arn
}
