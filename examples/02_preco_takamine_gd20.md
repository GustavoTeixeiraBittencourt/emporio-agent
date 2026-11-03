# Preço, parcelamento e promoção vencida

- Modelo: `openai/gpt-oss-120b`
- Base URL: `https://api.groq.com/openai/v1`
- Data/hora simulada (`AGENT_NOW`): `2026-03-23T11:10:00`

---

**Cliente:** quanto custa o Takamine GD20?

**Tom:** Takamine GD20 Dreadnought Natural: R$ 2.199,00 à vista (débito ou boleto).  
No PIX sai por R$ 2.089,05 (5 % de desconto).  
Parcelado em até 12x no cartão, a partir de R$ 183,25.  

Qualquer outra dúvida, é só chamar! 🎸

<details>
<summary>Chamadas de ferramentas</summary>

- `search_products({'category': 'Violões', 'query': 'Takamine GD20'})`
  → `{'available': [{'product_id': '95', 'name': 'Takamine GD20 Dreadnought Natural', 'category': 'Violões', 'price_brl': 2199.0, 'availability': 'available'}], 'unavailable_matches': []}`
- `get_payment_options({'product_id': '95'})`
  → `{'pix': {'price_brl': 2089.05, 'discount_applied': True}, 'debit': {'price_brl': 2199.0}, 'boleto': {'price_brl': 2199.0, 'settlement_business_days': 3}, 'credit_installments': [{'n': 1, 'installment_value_brl': 2199.0, 'eligible': True}, {'n': 2, 'installment_value_brl': 1099.5, 'eligible': True}, {'n': 3, 'installment_value_brl': 733.0, 'eligible': True}, {'n': 4, 'installment_value_brl': 549.75, 'eligible': True}, {'n': 5, 'installment_value_brl': 439.8, 'eligible': True}, {'n': 6, 'installment_value_brl': 366.5, 'eligible': True}, {'n': 7, 'installment_value_brl': 314.14, 'eligible': True}, {'n': 8, 'installment_value_brl': 274.88, 'eligible': True}, {'n': 9, 'installment_value_brl': 244.33, 'eligible': True}, {'n': 10, 'installment_value_brl': 219.9, 'eligible': True}, {'n': 11, 'installment_value_brl': 199.91, 'eligible': True}, {'n': 12, 'installment_value_brl': 183.25, 'eligible': True}], 'max_installments': 12, 'combined_payment_allowed': True}`

</details>

**Cliente:** dá pra parcelar? quero saber as opções de pagamento

**Tom:** Sim! Você pode pagar o Takamine GD20 assim:

- **PIX**: R$ 2.089,05 (5 % de desconto)  
- **Débito / Boleto**: R$ 2.199,00  
- **Cartão**: até 12x, a partir de R$ 183,25 por parcela  

Qualquer coisa, me avisa! 🎸

**Cliente:** vi uma promoção de 12% nesse violão, ainda vale?

**Tom:** No momento o nosso sistema não indica nenhuma promoção de 12 % para o Takamine GD20 – o preço que temos disponível é R$ 2.199,00 (com desconto de 5 % no PIX, como já mencionei).  

Se quiser, posso buscar outros violões que estejam em promoção agora. É só falar! 🎸

<details>
<summary>Chamadas de ferramentas</summary>

- `search_products({'category': 'Violões', 'query': 'Takamine GD20'})`
  → `{'available': [{'product_id': '95', 'name': 'Takamine GD20 Dreadnought Natural', 'category': 'Violões', 'price_brl': 2199.0, 'availability': 'available'}], 'unavailable_matches': []}`

</details>


---

## Extra: sair e voltar preserva o contexto

Trecho de uma sessão gravada à mão no CLI (sessão `3c32f91f`), **sem** `AGENT_NOW`
(relógio real), separada da conversa acima. Mostra que o histórico é salvo em
`.sessions/3c32f91f.json` e recarregado com `--session`.

```text
$ python -m emporio_agent
Tom -- Empório da Música (sessão: 3c32f91f). Digite /sair para encerrar.

Você: quanto custa o Takamine GD20?
Tom: Takamine GD20 Dreadnought Natural
- Preço à vista (PIX): R$ 2.089,05 (5 % de desconto)
- Preço à vista (débito/boleto): R$ 2.199,00
- Parcelado no cartão: até 12 x de R$ 183,25 (sem juros)

Quer saber mais detalhes ou outra opção? 🎶

Você: /sair

$ python -m emporio_agent --session 3c32f91f
Tom -- Empório da Música (sessão: 3c32f91f). Digite /sair para encerrar.

Você: da para parcelar ele
Tom: Sim, dá para parcelar o Takamine GD20 no cartão em até 12 x sem juros (parcela mínima de R$ 100,00). Por exemplo, 12 x de R$ 183,25. Se a compra for acima de R$ 2 000,00 você ainda pode combinar PIX (com 5 % de desconto) + cartão. Precisa de mais alguma coisa?
```

Na volta, o cliente disse apenas "ele": o Tom entendeu que era o Takamine GD20 sem
perguntar o produto de novo, porque o histórico da sessão foi recarregado do disco.
