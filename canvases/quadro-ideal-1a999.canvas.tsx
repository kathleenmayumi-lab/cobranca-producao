import {
  Callout,
  Divider,
  Grid,
  H1,
  H2,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

/** Quem trabalha esta no fone. 12 antes, 11 agora, 18 o alvo. */

export default function QuadroIdeal1a999() {
  return (
    <Stack gap={24} style={{ padding: 24, maxWidth: 720 }}>
      <Stack gap={8}>
        <H1 style={{ margin: 0 }}>18 pessoas no telefone</H1>
        <Text weight="semibold">
          Hoje 11. Arthur saiu. Acabou o Over. Todo mundo cobra 1 a 999.
          Quem trabalha esta no fone — nao tem gente na folha fora da
          ponta.
        </Text>
      </Stack>

      <Grid columns={3} gap={12}>
        <Stat value="18" label="O que precisamos" tone="success" />
        <Stat value="11" label="Hoje no telefone" />
        <Stat value="+7" label="A contratar" tone="warning" />
      </Grid>

      <Table
        headers={["", "Pessoas no telefone", "Acordo extra / dia"]}
        columnAlign={["left", "right", "right"]}
        striped
        rows={[
          ["Antes (duas celulas)", "12", "—"],
          ["Agora (Arthur fora)", "11", "—"],
          ["O que precisamos", "18", "+102 no 1–90 · +9 acima de 90"],
          ["Total a contratar", "+7", "~+111 se o discador apontar"],
        ]}
        rowTone={["neutral", "warning", "success", "info"]}
      />

      <Stack gap={8}>
        <H2 style={{ margin: 0 }}>Por que 18</H2>
        <Text>
          No 1 a 90, contratos ja discados no dia recebem 3,4 toques.
          Completar o 5o pede 15 pessoas — o furo e o Farfield. Acima
          de 90, 8 em 10 acordos saem na primeira ligacao: pede 3
          pessoas para nao deixar de ligar, nao 15 para reciclar.
          15 + 3 = 18, no mesmo discador.
        </Text>
      </Stack>
      <Table
        headers={["Faixa", "O que a operacao faz", "Gente"]}
        columnAlign={["left", "left", "right"]}
        striped
        rows={[
          ["1 a 90", "Ja toma 3,4 toques. Falta o 5o, principalmente Farfield", "15"],
          ["91 a 999", "Acordo na 1a ligacao. Reciclar nao fecha", "3"],
          ["5 toques em 61 mil contratos", "Fundo de fila nao paga o 5o toque", "34 — nao"],
          ["Total", "Um time, 1 a 999", "18"],
        ]}
        rowTone={["success", "success", "danger", "info"]}
      />

      <Divider />

      <Stack gap={8}>
        <H2 style={{ margin: 0 }}>Ate onde vale discar</H2>
        <Text>
          Cadeira = R$ 8.320/mes (R$ 8.000 salario + R$ 319,90 ramal
          ilimitado). R$ 378/dia. No 1 a 90 o custo por acordo nao
          sobe (~R$ 19–22); o volume some. Acima de 90 o custo sobe
          na 2a (R$ 69 → R$ 108) e o acordo zera na 6a.
        </Text>
      </Stack>
      <Table
        headers={[
          "Toque",
          "Acordos/dia",
          "Custo/dia",
          "Custo/acordo",
          "Vaga?",
        ]}
        columnAlign={["left", "right", "right", "right", "left"]}
        striped
        rows={[
          ["5ª · 1 a 90", "17,2", "R$ 340", "R$ 20", "Sim — quadro 15"],
          ["7ª · 1 a 90", "7,7", "R$ 146", "R$ 19", "Nao — 0,39 cadeira"],
          ["8ª · 1 a 90", "5,2", "R$ 98", "R$ 19", "Nao — 0,26 cadeira"],
          ["12ª · 1 a 90", "1,1", "R$ 20", "R$ 19", "Nao — ~1 acordo/dia"],
          ["1ª · acima de 90", "10,8", "R$ 748", "R$ 69", "Sim — quadro 3"],
          ["2ª · acima de 90", "1,2", "R$ 131", "R$ 108", "Nao reciclar"],
          ["6ª+ · acima de 90", "0", "R$ 0", "—", "Zero acordo"],
          ["Total (corte)", "—", "—", "—", "Para no 5o Early e na 1a Over"],
        ]}
        rowTone={[
          "success",
          "danger",
          "danger",
          "danger",
          "success",
          "warning",
          "danger",
          "info",
        ]}
      />
      <Text tone="secondary" size="small">
        7o toque: R$ 140 salario + R$ 6 ramal por dia. Mesmo R$ 19 por
        acordo da 1a. Nao abre vaga porque nao e pessoa e porque
        recicla quem ja tomou 5 — Farfield ainda esta em 1,4% no 5o.
      </Text>

      <Divider />

      <Stack gap={8}>
        <H2 style={{ margin: 0 }}>O que o discador tem que fazer</H2>
        <Text>
          Sem celula Over, o peso decide. Se continuar 40 no 1 a 30, a
          gente nova liga de novo em quem ja atende e o atraso alto some.
        </Text>
      </Stack>
      <Table
        headers={["Lista", "Fazer"]}
        columnAlign={["left", "left"]}
        striped
        rows={[
          ["Farfield / 31–60 / 61–90", "Reciclar. Quase todo o +102 esta aqui"],
          ["1 a 30", "Nao tirar ligacao. Primeira tentativa e 36,6% da loja"],
          ["91 a 180", "Garantir o primeiro toque"],
          ["Fresh, STARS Over, >180", "Nao subir. Ja gira ou nao fecha"],
          ["Total", "Contratar sem mexer o discador nao resolve"],
        ]}
        rowTone={["success", "warning", "success", "danger", "info"]}
      />

      <Table
        headers={["", "Pessoas", "R$/mes"]}
        columnAlign={["left", "right", "right"]}
        striped
        rows={[
          ["Hoje", "11", "91,5 mil"],
          ["18 no telefone", "18", "149,8 mil"],
          ["Total", "+7", "+58 mil"],
        ]}
        rowTone={["warning", "success", "info"]}
      />

      <Callout tone="success" title="Recomendacao">
        Ampliar o quadro de 11 para 18 analistas no discador, campanha
        unica 1 a 999. No 1 a 90, completar o 5o toque (Farfield).
        Acima de 90, assegurar a primeira ligacao. Nao contratar 34.
      </Callout>
    </Stack>
  );
}
