terraform {
  backend "s3" {
    bucket  = "entso-scraper-terraform-state"
    key     = "demo/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }
}
