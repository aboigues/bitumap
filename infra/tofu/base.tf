# Base Serverless SQL (002 T077) : 0 vCPU au repos (principe II), mise en veille après
# 5 min sans requête ; seul le stockage est facturé au repos (≈ 0,20 €/Go/mois).
resource "scaleway_sdb_sql_database" "bitumap" {
  name    = "bitumap"
  min_cpu = 0
  max_cpu = 2
}
