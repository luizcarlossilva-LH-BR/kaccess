/**
 * KeyAccess - Processar planilha e enviar eventos (Google Apps Script)
 * Equivalente ao process_and_send.py, rodando direto no GCP/Google Sheets.
 *
 * CONFIGURAÇÃO (OBRIGATÓRIO antes de usar):
 * 1. Em "Project Settings" > "Script Properties", adicione as chaves abaixo:
 *    - KEYACCESS_CLIENT_ID         (ex: companyshopee)
 *    - KEYACCESS_CLIENT_SECRET     (chave secreta fornecida pela equipe KeyAccess)
 *    - KEYACCESS_COMPANY_INSTANCE  (ex: companylogsbcshopee)
 *    - KEYACCESS_HOST_REF_ID       (ex: 2559690)
 *    - KEYACCESS_SPREADSHEET_ID    (ID da planilha Google, opcional se abrir pelo menu)
 * 2. Opcionalmente, defina também:
 *    - KEYACCESS_BASE_URL  (padrão: https://api.visitantes.online/api)
 *    - KEYACCESS_AUTH_URL  (padrão: https://visitantes.online/auth/login/client)
 *
 * ATENÇÃO: NÃO coloque credenciais diretamente no código.
 *          Use exclusivamente as Script Properties acima.
 */

// Valores padrão APENAS para URLs públicas (sem credenciais).
var CONFIG_DEFAULTS = {
  BASE_URL: 'https://api.visitantes.online/api',
  AUTH_URL: 'https://visitantes.online/auth/login/client',
};

function getConfig() {
  var p = PropertiesService.getScriptProperties();
  return {
    clientId:        p.getProperty('KEYACCESS_CLIENT_ID')        || '',
    clientSecret:    p.getProperty('KEYACCESS_CLIENT_SECRET')    || '',
    companyInstance: p.getProperty('KEYACCESS_COMPANY_INSTANCE') || '',
    baseUrl:        (p.getProperty('KEYACCESS_BASE_URL')  || CONFIG_DEFAULTS.BASE_URL).replace(/\/$/, ''),
    authUrl:         p.getProperty('KEYACCESS_AUTH_URL')  || CONFIG_DEFAULTS.AUTH_URL,
    hostRefId:       parseInt(p.getProperty('KEYACCESS_HOST_REF_ID') || '0', 10),
    spreadsheetId:   p.getProperty('KEYACCESS_SPREADSHEET_ID') || ''
  };
}

/**
 * Valida se todas as propriedades obrigatórias estão configuradas.
 * @param {Object} config
 * @returns {string[]} Lista de chaves ausentes (vazia se tudo ok)
 */
function getMissingConfigKeys(config) {
  var required = {
    'KEYACCESS_CLIENT_ID':        config.clientId,
    'KEYACCESS_CLIENT_SECRET':    config.clientSecret,
    'KEYACCESS_COMPANY_INSTANCE': config.companyInstance,
    'KEYACCESS_HOST_REF_ID':      config.hostRefId
  };
  return Object.keys(required).filter(function(k) { return !required[k]; });
}

/**
 * Converte data e hora (America/Sao_Paulo) para ISO 8601 UTC.
 * @param {string} dateStr - "YYYY-MM-DD"
 * @param {string} timeStr - "HH:MM"
 * @returns {string|null} "YYYY-MM-DDTHH:mm:ssZ" ou null
 */
function formatDateIsoUtc(dateStr, timeStr) {
  try {
    // São Paulo = UTC-3 (fixo desde 2019)
    var isoLocal = dateStr + 'T' + timeStr + ':00-03:00';
    var d = new Date(isoLocal);
    if (isNaN(d.getTime())) return null;
    return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
  } catch (e) {
    Logger.log('Warning: Could not parse date ' + dateStr + ' ' + timeStr);
    return null;
  }
}

/**
 * Autentica na API KeyAccess (Client Credentials).
 * @returns {string|null} access_token ou null
 */
function keyAccessLogin(config) {
  var credentials = Utilities.base64Encode(config.clientId + ':' + config.clientSecret);
  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Basic ' + credentials },
    payload: JSON.stringify({
      grant_type: 'client_credentials',
      scope: 'cloud-system-rw'
    }),
    muteHttpExceptions: true
  };
  var response = UrlFetchApp.fetch(config.authUrl, options);
  var code = response.getResponseCode();
  var body = JSON.parse(response.getContentText());
  if (code < 200 || code >= 300) {
    Logger.log('Login failed: ' + code + ' ' + response.getContentText());
    return null;
  }
  return body.access_token || null;
}

/**
 * Cria um evento na API KeyAccess.
 * @param {Object} config - config com baseUrl, companyInstance
 * @param {string} token - Bearer token
 * @param {Object} payload - corpo do evento
 * @returns {Object|null} resposta JSON ou null
 */
function keyAccessCreateEvent(config, token, payload) {
  var url = config.baseUrl + '/logistics/' + config.companyInstance + '/events';
  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      'Content-Type': 'application/json'
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();
  var text = response.getContentText();
  if (code < 200 || code >= 300) {
    Logger.log('Error creating event: ' + code + ' ' + text);
    return null;
  }
  return text ? JSON.parse(text) : {};
}

/**
 * Encontra o índice da linha de cabeçalho (contém "titulo" ou "sentido").
 */
function findHeaderRowIndex(values) {
  for (var i = 0; i < values.length; i++) {
    var row = values[i].map(function (x) { return String(x).toLowerCase(); });
    if (row.indexOf('titulo') !== -1 || row.indexOf('sentido') !== -1) {
      return i;
    }
  }
  return -1;
}

/**
 * Normaliza CPF: só dígitos, 11 caracteres (zeros à esquerda).
 */
function formatCpf(cpf) {
  var raw = String(cpf).replace(/\./g, '').replace(/-/g, '').replace(/\s/g, '');
  while (raw.length < 11) raw = '0' + raw;
  return raw.slice(0, 11);
}

/**
 * Índice da coluna por nome (case-insensitive).
 */
function getColumnIndex(headers, colName) {
  var lower = colName.toLowerCase();
  for (var i = 0; i < headers.length; i++) {
    if (String(headers[i]).toLowerCase() === lower) return i;
  }
  return -1;
}

/**
 * Obtém valor da célula por nome da coluna (case-insensitive).
 */
function getCell(row, headers, colName) {
  var i = getColumnIndex(headers, colName);
  if (i === -1) return '';
  return row[i] !== undefined && row[i] !== null ? String(row[i]).trim() : '';
}

function showResult(msg) {
  Logger.log(msg);
  try {
    var ui = SpreadsheetApp.getUi();
    if (ui) ui.alert(msg);
    else SpreadsheetApp.getActiveSpreadsheet().toast(msg, 'KeyAccess', 8);
  } catch (e) {
    SpreadsheetApp.getActiveSpreadsheet().toast(msg, 'KeyAccess', 8);
  }
}

function main() {
  var config = getConfig();

  // Validação antecipada: falha com mensagem clara se credenciais não configuradas
  var missing = getMissingConfigKeys(config);
  if (missing.length > 0) {
    var msg = 'ERRO DE CONFIGURAÇÃO: As seguintes Script Properties obrigatórias não estão definidas:\n'
            + missing.join('\n')
            + '\n\nAcesse: Configurações do projeto > Propriedades do script';
    showResult(msg);
    return;
  }

  var token = keyAccessLogin(config);
  if (!token) {
    showResult('ERRO: Falha no login KeyAccess. Verifique credenciais e URLs. Veja o Log em Execuções.');
    return;
  }

  var spreadsheet;
  if (config.spreadsheetId) {
    spreadsheet = SpreadsheetApp.openById(config.spreadsheetId);
  } else {
    spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  }
  if (!spreadsheet) {
    showResult('ERRO: Nenhuma planilha ativa. Abra a planilha ou defina KEYACCESS_SPREADSHEET_ID.');
    return;
  }

  var sheet = spreadsheet.getActiveSheet();
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2 || lastCol < 1) {
    showResult('Nenhum dado na planilha (precisa de cabeçalho + pelo menos 1 linha).');
    return;
  }

  var range = sheet.getRange(1, 1, lastRow, Math.max(lastCol, 26));
  var values = range.getValues();

  var headerIndex = findHeaderRowIndex(values);
  if (headerIndex === -1) {
    showResult("Cabeçalho não encontrado. A planilha precisa de uma linha com 'Titulo' ou 'sentido'.");
    return;
  }

  var headers = values[headerIndex].map(function (h) { return String(h).trim(); });
  var dataRows = values.slice(headerIndex + 1);
  var successCount = 0;
  var failCount = 0;

  Logger.log('Processing ' + dataRows.length + ' rows...');

  for (var r = 0; r < dataRows.length; r++) {
    var row = dataRows[r];
    // Garantir mesmo número de colunas que o header
    while (row.length < headers.length) row.push('');
    if (row.length > headers.length) row = row.slice(0, headers.length);

    var sentido = getCell(row, headers, 'sentido').toUpperCase();
    var behavior = sentido === 'SAIDA' ? 'EXIT' : 'ENTRY';

    var dateStr = getCell(row, headers, 'data');
    var horaInicio = getCell(row, headers, 'hora_inicio');
    var horaFim = getCell(row, headers, 'hora_fim');
    var startAt = formatDateIsoUtc(dateStr, horaInicio);
    var endAt = formatDateIsoUtc(dateStr, horaFim);

    if (!startAt || !endAt) {
      Logger.log('Row ' + (r + 2) + ': Skipping due to date error.');
      failCount++;
      continue;
    }

    var cpf = formatCpf(getCell(row, headers, 'cpf'));
    var titulo = getCell(row, headers, 'titulo');
    var driverName = getCell(row, headers, 'driver_name');
    var placa = getCell(row, headers, 'placa_veiculo');
    var nomeAjudante = getCell(row, headers, 'nome_ajudante');
    var docAjudante = getCell(row, headers, 'doc_ajudante');

    var payload = {
      title: titulo,
      startAt: startAt,
      endAt: endAt,
      behavior: behavior,
      target: 'LOGISTIC',
      autoRelease: true,
      hostRefId: config.hostRefId,
      driver: {
        fullName: driverName,
        document: cpf,
        licensePlateOne: placa,
        onFoot: false
      },
      assistants: []
    };

    if (nomeAjudante && nomeAjudante !== '-' && nomeAjudante.toLowerCase() !== 'nan') {
      payload.assistants.push({
        fullName: nomeAjudante,
        document: docAjudante === '-' ? '' : docAjudante
      });
    }

    Logger.log('Sending event for driver: ' + driverName);
    var result = keyAccessCreateEvent(config, token, payload);
    if (result) {
      Logger.log('SUCCESS! Event Created.');
      if (result.fullPathLocator) Logger.log('Link: ' + result.fullPathLocator);
      successCount++;
    } else {
      Logger.log('FAILED.');
      failCount++;
    }
  }

  var total = dataRows.length;
  var msg = 'Concluído. Sucesso: ' + successCount + ', Falha: ' + failCount + ', Total linhas: ' + total;
  Logger.log(msg);
  showResult(msg);
}

/**
 * Menu no Google Sheets: Executar > KeyAccess: Processar e enviar
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('KeyAccess')
    .addItem('Processar e enviar', 'main')
    .addToUi();
}
