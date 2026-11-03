# Catálogo: violões até R$1000

- Modelo: `openai/gpt-oss-120b`
- Base URL: `https://api.groq.com/openai/v1`
- Data/hora simulada (`AGENT_NOW`): `2026-03-23T11:00:00`

---

**Cliente:** oi! quais violões vocês têm até R$1000?

**Tom:** Oi! Temos várias opções de violões até R$ 1 000. Aqui vão 5 modelos disponíveis:

1. **Yamaha C40 Nylon – Natural** – R$ 599,90  
2. **Yamaha C70 Nylon – Natural** – R$ 849,00  
3. **Tagima Memphis AC‑39 Nylon – Natural** – R$ 429,90  
4. **Giannini GN‑15 Nylon – Cedro Natural** – R$ 689,00  
5. **Yamaha F310 Aço – Natural** – R$ 699,90  

Qual desses te interessa mais? 😊  

<details>
<summary>Chamadas de ferramentas</summary>

- `search_products({'category': 'Violões', 'max_price': 1000})`
  → `{'available': [{'product_id': '81', 'name': 'Yamaha C40 Nylon Natural', 'category': 'Violões', 'price_brl': 599.9, 'availability': 'available'}, {'product_id': '82', 'name': 'Yamaha C70 Nylon Natural', 'category': 'Violões', 'price_brl': 849.0, 'availability': 'available'}, {'product_id': '83', 'name': 'Tagima Memphis AC-39 Nylon Natural', 'category': 'Violões', 'price_brl': 429.9, 'availability': 'available'}, {'product_id': '84', 'name': 'Giannini GN-15 Nylon Cedr Natural', 'category': 'Violões', 'price_brl': 689.0, 'availability': 'available'}, {'product_id': '85', 'name': 'Rozini RC-104 Nylon Estudante', 'category': 'Violões', 'price_brl': 459.9, 'availability': 'available'}, {'product_id': '86', 'name': 'Tagima Dallas Tuner Aço Natural', 'category': 'Violões', 'price_brl': 749.0, 'availability': 'available'}, {'product_id': '87', 'name': 'Yamaha F310 Aço Natural', 'category': 'Violões', 'price_brl': 699.9, 'availability': 'available'}, {'product_id': '88', 'name': 'Giannini GF-1R Aço Folk Sunburst', 'category': 'Violões', 'price_brl': 579.9, 'availability': 'available'}, {'product_id': '89', 'name': 'Shelby SN-100 Folk Aço Preto', 'category': 'Violões', 'price_brl': 549.0, 'availability': 'available'}, {'product_id': '91', 'name': 'Tagima Woodstock Dreadnought Natural', 'category': 'Violões', 'price_brl': 899.0, 'availability': 'available'}, {'product_id': '107', 'name': 'Shelby SGD-195E Elétrico Aço Sunburst', 'category': 'Violões', 'price_brl': 799.0, 'availability': 'available'}, {'product_id': '112', 'name': 'Tagima TW-7 7 Cordas Aço Natural', 'category': 'Violões', 'price_brl': 999.0, 'availability': 'available'}], 'unavailable_matches': [{'product_id': '96', 'name': 'Giannini GF-3D Dreadnought Sunburst', 'category': 'Violões', 'price_brl': 799.9, 'availability': 'out_of_stock'}, {'product_id': '113', 'name': 'Shelby SN-7C 7 Cordas Nylon Natural', 'category': 'Violões', 'price_brl': 749.0, 'availability': 'discontinued'}]}`

</details>

**Cliente:** algum deles é eletroacústico?

**Tom:** Sim! Temos um modelo eletroacústico dentro do seu limite:

- **Shelby SGD‑195E Elétrico Aço – Sunburst** – R$ 799,00 (disponível)

Quer saber as opções de pagamento ou mais detalhes? 🎸

<details>
<summary>Chamadas de ferramentas</summary>

- `search_products({'category': 'Violões', 'electric': True})`
  → `{'available': [{'product_id': '94', 'name': 'Taylor 110e Dreadnought Natural', 'category': 'Violões', 'price_brl': 5519.08, 'availability': 'available', 'original_price_brl': 5999.0, 'discount_percent': 8}, {'product_id': '98', 'name': 'Yamaha NTX1 Elétrico Nylon Natural', 'category': 'Violões', 'price_brl': 3499.0, 'availability': 'available'}, {'product_id': '99', 'name': 'Tagima Classical Elétrico Nylon Sunburst', 'category': 'Violões', 'price_brl': 1199.0, 'availability': 'available'}, {'product_id': '100', 'name': 'Takamine GC5CE Elétrico Nylon Natural', 'category': 'Violões', 'price_brl': 3299.0, 'availability': 'available'}, {'product_id': '101', 'name': 'Giannini GNF-3 CEQ Elétrico Nylon Natural', 'category': 'Violões', 'price_brl': 1049.0, 'availability': 'available'}, {'product_id': '102', 'name': 'Crafter CE-15 Elétrico Nylon Natural', 'category': 'Violões', 'price_brl': 3899.0, 'availability': 'low_stock', 'note': 'poucas unidades em estoque'}, {'product_id': '103', 'name': 'Tagima Vegas Elétrico Aço Natural', 'category': 'Violões', 'price_brl': 1349.0, 'availability': 'available'}, {'product_id': '104', 'name': 'Yamaha APX600 Elétrico Aço Preto', 'category': 'Violões', 'price_brl': 1899.0, 'availability': 'available'}, {'product_id': '105', 'name': 'Takamine GN51CE Elétrico Aço Natural', 'category': 'Violões', 'price_brl': 4199.0, 'availability': 'available'}, {'product_id': '106', 'name': 'Taylor 214ce Elétrico Aço Natural', 'category': 'Violões', 'price_brl': 7499.0, 'availability': 'low_stock', 'note': 'poucas unidades em estoque'}, {'product_id': '107', 'name': 'Shelby SGD-195E Elétrico Aço Sunburst', 'category': 'Violões', 'price_brl': 799.0, 'availability': 'available'}, {'product_id': '108', 'name': 'Martin D-28E Elétrico Aço Natural', 'category': 'Violões', 'price_brl': 12000.0, 'availability': 'low_stock', 'note': 'poucas unidades em estoque'}, {'product_id': '111', 'name': 'Rozini RV-175 7 Cordas Elétrico Natural', 'category': 'Violões', 'price_brl': 1699.0, 'availability': 'available'}, {'product_id': '115', 'name': 'Takamine GC1CE Elétrico Nylon Natural', 'category': 'Violões', 'price_brl': 2499.0, 'availability': 'available'}], 'unavailable_matches': []}`

</details>

