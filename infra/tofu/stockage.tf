# Buckets (002 T076, 003 T040/T095). Les noms de bucket sont uniques sur tout Scaleway :
# suffixe aléatoire, noms transmis à l'application par BITUMAP_BUCKET_… (PR B).
resource "random_id" "suffixe_buckets" {
  byte_length = 4
}

locals {
  suffixe = random_id.suffixe_buckets.hex
  lecture = ["s3:GetObject", "s3:ListBucket"]
  ecriture = [
    "s3:GetObject", "s3:ListBucket", "s3:PutObject", "s3:DeleteObject",
  ]
}

# Rapports : privé, versionné ; anciennes versions gardées 30 jours (coût borné).
resource "scaleway_object_bucket" "rapports" {
  name = "bitumap-rapports-${local.suffixe}"
  tags = { application = "bitumap", contenu = "rapports" }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    id      = "anciennes-versions"
    enabled = true
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload_days = 1
  }
}

# Cache des sources : privé, régénérable, expiration à 30 jours.
resource "scaleway_object_bucket" "cache" {
  name = "bitumap-cache-${local.suffixe}"
  tags = { application = "bitumap", contenu = "cache" }

  lifecycle_rule {
    id      = "expiration"
    enabled = true
    expiration {
      days = 30
    }
    abort_incomplete_multipart_upload_days = 1
  }
}

# Photos des relevés terrain (003 R1, R12) : privé, versionné, conservées sans limite ;
# la quarantaine (originaux avec EXIF) expire à 1 jour, versions non courantes et marqueurs
# de suppression compris (LL-013).
resource "scaleway_object_bucket" "terrain" {
  name = "bitumap-terrain-${local.suffixe}"
  tags = { application = "bitumap", contenu = "terrain" }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    id      = "quarantaine"
    prefix  = "quarantaine/"
    enabled = true
    expiration {
      days = 1
    }
    noncurrent_version_expiration {
      noncurrent_days = 1
    }
  }

  lifecycle_rule {
    id      = "quarantaine-marqueurs"
    prefix  = "quarantaine/"
    enabled = true
    expiration {
      expired_object_delete_marker = true
    }
  }

  lifecycle_rule {
    id                                     = "envois-incomplets"
    enabled                                = true
    abort_incomplete_multipart_upload_days = 1
  }

  # Envoi présigné depuis le navigateur (003 R4) : origine du service seulement.
  cors_rule {
    allowed_methods = ["POST"]
    allowed_origins = [local.url_publique]
    allowed_headers = ["*"]
    max_age_seconds = 3600
  }
}

# Politiques de bucket : une fois posée, seuls les principaux listés ont accès. bitumap-tofu
# garde l'administration ; l'API et le job n'ont que ce dont ils ont besoin.
resource "scaleway_object_bucket_policy" "rapports" {
  bucket = scaleway_object_bucket.rapports.name
  policy = jsonencode({
    Version = "2023-04-17"
    Id      = "bitumap-rapports"
    Statement = [
      {
        Sid       = "Administration"
        Effect    = "Allow"
        Principal = { SCW = local.principal_tofu }
        Action    = ["s3:*"]
        Resource  = [scaleway_object_bucket.rapports.name, "${scaleway_object_bucket.rapports.name}/*"]
      },
      {
        Sid       = "ApiLecture"
        Effect    = "Allow"
        Principal = { SCW = local.principal_api }
        Action    = local.lecture
        Resource  = [scaleway_object_bucket.rapports.name, "${scaleway_object_bucket.rapports.name}/*"]
      },
      {
        Sid       = "JobEcriture"
        Effect    = "Allow"
        Principal = { SCW = local.principal_job }
        Action    = local.ecriture
        Resource  = [scaleway_object_bucket.rapports.name, "${scaleway_object_bucket.rapports.name}/*"]
      },
    ]
  })
}

resource "scaleway_object_bucket_policy" "cache" {
  bucket = scaleway_object_bucket.cache.name
  policy = jsonencode({
    Version = "2023-04-17"
    Id      = "bitumap-cache"
    Statement = [
      {
        Sid       = "Administration"
        Effect    = "Allow"
        Principal = { SCW = local.principal_tofu }
        Action    = ["s3:*"]
        Resource  = [scaleway_object_bucket.cache.name, "${scaleway_object_bucket.cache.name}/*"]
      },
      {
        Sid       = "JobEcriture"
        Effect    = "Allow"
        Principal = { SCW = local.principal_job }
        Action    = local.ecriture
        Resource  = [scaleway_object_bucket.cache.name, "${scaleway_object_bucket.cache.name}/*"]
      },
    ]
  })
}

resource "scaleway_object_bucket_policy" "terrain" {
  bucket = scaleway_object_bucket.terrain.name
  policy = jsonencode({
    Version = "2023-04-17"
    Id      = "bitumap-terrain"
    Statement = [
      {
        Sid       = "Administration"
        Effect    = "Allow"
        Principal = { SCW = local.principal_tofu }
        Action    = ["s3:*"]
        Resource  = [scaleway_object_bucket.terrain.name, "${scaleway_object_bucket.terrain.name}/*"]
      },
      {
        # Photos : dépôt présigné, réencodage, lecture, retrait RGPD (toutes les versions).
        Sid       = "ApiPhotos"
        Effect    = "Allow"
        Principal = { SCW = local.principal_api }
        Action = concat(local.ecriture, [
          "s3:GetObjectVersion", "s3:ListBucketVersions", "s3:DeleteObjectVersion",
        ])
        Resource = [scaleway_object_bucket.terrain.name, "${scaleway_object_bucket.terrain.name}/*"]
      },
    ]
  })
}
