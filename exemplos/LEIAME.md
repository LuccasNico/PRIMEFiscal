# Notas fiscais de exemplo

Pares PDF + XML com **dados fictícios**, obtidos dos testes da biblioteca
[Engenere/BrazilFiscalReport](https://github.com/Engenere/BrazilFiscalReport) (licença LGPL-3.0),
baixados em 12/10/2026. O XML é o gabarito para avaliar a extração do PDF correspondente.

| Arquivo | Tipo | Original no repositório (PDF / XML) | Observação |
|---|---|---|---|
| 01_nfe_basica | NF-e | danfe_default.pdf / nfe_test_1.xml | 1 item |
| 02_nfe_simples_nacional | NF-e | danfe_sn.pdf / nfe_test_sn.xml | Simples Nacional |
| 03_nfe_reforma_tributaria | NF-e | danfe_reforma_tributaria.pdf / nfe_reforma_tributaria.xml | IBS/CBS |
| 04_nfe_multipagina_paisagem | NF-e | danfe_multipage_landscape.pdf / nfe_multi_page_products_landscape.xml | 29 itens, 3 páginas; o texto extraído sai invertido (página girada) |
| 05_nfce_basica | NFC-e | danfce_default.pdf / danfce_default.xml | 3 itens |
| 06_nfce_muitos_itens | NFC-e | danfce_many_items.pdf / danfce_many_items.xml | 36 itens |
| 07_nfce_sem_consumidor | NFC-e | danfce_without_consumer.pdf / danfce_without_consumer.xml | Consumidor não identificado |
| 08_nfse_homologacao | NFS-e | danfse_default_hom.pdf / nfse_test_hom.xml | Padrão nacional, homologação |
| 09_nfse_com_intermediario | NFS-e | danfse_intermediary.pdf / nfse_test_interm.xml | Com intermediário |
| 10_nfse_reforma_tributaria | NFS-e | danfse_rtc_valid.pdf / nfse_rtc_valid.xml | IBS/CBS |

**Limitações:** todos os PDFs foram gerados pela mesma biblioteca (nenhum é digitalizado) e as
NFS-e seguem só o layout do padrão nacional. O dataset final do TCC deve incluir notas reais e variadas.
