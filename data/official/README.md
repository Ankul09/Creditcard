# Drop official documents here

Put official issuer documents in this folder (any subfolder layout), e.g.
  data/official/hdfc/regalia-gold-mitc.pdf
  data/official/sbi/titan-tnc.pdf
  data/official/axis/magnus-feeschedule.pdf
Name files after the card where possible. Then tell Claude "ingest data/official" and each document will be
read, the matching card record updated (confidence high only when rates, caps, exclusions AND fees come
from the document), and the change logged in `verification.changes`.
Official documents always override web-collected data.
