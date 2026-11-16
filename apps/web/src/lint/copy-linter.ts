export type CopyLintFinding = {
  phrase: string;
  line: number;
  column: number;
  excerpt: string;
};

type PhraseRule = {
  phrase: string;
  expression: RegExp;
  allowedPrefix: RegExp[];
};

const rules: PhraseRule[] = [
  {
    phrase: "predicción",
    expression: /(?<![\p{L}\p{N}_])predicción(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bno\s+(?:es|constituye|representa)\s+(?:una\s+)?$/iu,
    ],
  },
  {
    phrase: "pronóstico",
    expression: /(?<![\p{L}\p{N}_])pronóstico(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bno\s+(?:es|constituye|representa)\s+(?:(?:un|el)\s+)?$/iu,
      /\bni\s+(?:(?:un|el)\s+)?$/iu,
    ],
  },
  {
    phrase: "rendimiento esperado",
    expression: /(?<![\p{L}\p{N}_])rendimiento\s+esperado(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bno\s+(?:calcula|estima|afirma|predice|reporta)\s+(?:(?:el|un)\s+)?$/iu,
    ],
  },
  {
    phrase: "garantiza",
    expression: /(?<![\p{L}\p{N}_])garantiza(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [/\bno\s+$/iu],
  },
  {
    phrase: "mejor estrategia",
    expression: /(?<![\p{L}\p{N}_])mejor\s+estrategia(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bno\s+(?:es|determina|identifica|recomienda)\s+(?:(?:la|una)\s+)?$/iu,
    ],
  },
  {
    phrase: "déficit real",
    expression: /(?<![\p{L}\p{N}_])déficit\s+real(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bno\s+(?:es|mide|representa|estima|calcula)\s+(?:(?:un|el)\s+)?$/iu,
    ],
  },
  {
    phrase: "prediction (English)",
    expression: /(?<![\p{L}\p{N}_])prediction(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [/\bnot\s+(?:a\s+)?$/iu],
  },
  {
    phrase: "forecast (English)",
    expression: /(?<![\p{L}\p{N}_])forecast(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bnot\s+(?:a\s+)?$/iu,
      /\b(?:or|nor)\s+(?:a\s+)?$/iu,
    ],
  },
  {
    phrase: "expected yield (English)",
    expression: /(?<![\p{L}\p{N}_])expected\s+yield(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bdoes\s+not\s+(?:calculate|estimate|report|predict)\s+(?:(?:the|an)\s+)?$/iu,
    ],
  },
  {
    phrase: "guarantee (English)",
    expression: /(?<![\p{L}\p{N}_])guarantee(?:s|d)?(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bdoes\s+not\s+$/iu,
      /\bnot\s+(?:be\s+)?$/iu,
    ],
  },
  {
    phrase: "best strategy (English)",
    expression: /(?<![\p{L}\p{N}_])best\s+strategy(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bdoes\s+not\s+(?:identify|select|recommend)\s+(?:(?:the|a)\s+)?$/iu,
      /\bnot\s+(?:(?:the|a)\s+)?$/iu,
    ],
  },
  {
    phrase: "real/actual deficit (English)",
    expression: /(?<![\p{L}\p{N}_])(?:real|actual)\s+deficit(?![\p{L}\p{N}_])/giu,
    allowedPrefix: [
      /\bdoes\s+not\s+(?:measure|represent|estimate|calculate)\s+(?:(?:a|an|the)\s+)?$/iu,
      /\bnot\s+(?:(?:a|an|the)\s+)?$/iu,
    ],
  },
];

function sentenceStart(text: string, index: number): number {
  const boundary = Math.max(
    text.lastIndexOf(".", index - 1),
    text.lastIndexOf("?", index - 1),
    text.lastIndexOf("!", index - 1),
    text.lastIndexOf(";", index - 1),
    text.lastIndexOf("\n", index - 1),
  );
  return boundary + 1;
}

function isAllowedByContext(text: string, start: number, rule: PhraseRule): boolean {
  const startOfSentence = sentenceStart(text, start);
  const prefix = text.slice(startOfSentence, start);

  // A negation only excuses the occurrence it governs. A positive claim later in
  // the same sentence remains reportable, even if an earlier phrase was negated.
  return rule.allowedPrefix.some((pattern) => pattern.test(prefix));
}

function lineAndColumn(text: string, index: number): { line: number; column: number } {
  const preceding = text.slice(0, index);
  const lastNewline = preceding.lastIndexOf("\n");
  return {
    line: (preceding.match(/\n/gu)?.length ?? 0) + 1,
    column: index - lastNewline,
  };
}

/** Find prohibited product claims while allowing explicit, local disclaimers. */
export function lintCopy(text: string): CopyLintFinding[] {
  const findings: CopyLintFinding[] = [];

  for (const rule of rules) {
    rule.expression.lastIndex = 0;
    for (const match of text.matchAll(rule.expression)) {
      const index = match.index;
      const end = index + match[0].length;
      if (isAllowedByContext(text, index, rule)) continue;

      const { line, column } = lineAndColumn(text, index);
      const excerpt = text.slice(Math.max(0, index - 48), Math.min(text.length, end + 48)).replace(/\s+/gu, " ").trim();
      findings.push({ phrase: rule.phrase, line, column, excerpt });
    }
  }

  return findings.sort((a, b) => a.line - b.line || a.column - b.column);
}
