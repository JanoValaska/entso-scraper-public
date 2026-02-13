module "fck-nat" {
  source  = "RaJiska/fck-nat/aws"
  version = "1.4.0"

  name                = "${var.project}-${var.environment}-nat"
  vpc_id              = var.vpc_id
  subnet_id           = var.public_subnet_id
  instance_type       = var.instance_type
  ha_mode             = var.ha
  update_route_tables = false # Keep your custom route tables
}

resource "aws_route_table" "private" {
  vpc_id = var.vpc_id

  route {
    cidr_block           = "0.0.0.0/0"
    network_interface_id = module.fck-nat.eni_id
  }

  tags = {
    Name        = "${var.project}-private-rt-${var.environment}"
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_route_table_association" "private" {
  count          = length(var.private_subnet_ids)
  subnet_id      = var.private_subnet_ids[count.index]
  route_table_id = aws_route_table.private.id
}
