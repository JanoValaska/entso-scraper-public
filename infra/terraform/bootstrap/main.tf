module "tf_state" {
  source      = "../modules/s3"
  bucket_name = var.state_bucket_name
  project     = local.project
  versioning  = true
}

