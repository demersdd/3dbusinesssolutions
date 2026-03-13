export default {
  async fetch(request, env) {
    const allowedOrigins = [
      'https://3dbusinesssolutions.com',
      'https://www.3dbusinesssolutions.com',
      'http://localhost',
      'http://127.0.0.1'
    ];
    const origin = request.headers.get('Origin') || '';
    const corsOrigin = allowedOrigins.includes(origin) ? origin : allowedOrigins[0];
    const corsHeaders = {
      'Access-Control-Allow-Origin': corsOrigin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405, headers: corsHeaders });
    }

    try {
      const body = await request.json();

      // Route to OpenSanctions (with retry + exponential backoff for 429s)
      if (body._service === 'opensanctions') {
        const { _service, _path, ...payload } = body;
        const url = `https://api.opensanctions.org${_path}`;

        let lastResponse;
        for (let attempt = 0; attempt < 4; attempt++) {
          if (attempt > 0) {
            // Respect Retry-After header if present, otherwise exponential backoff
            const retryAfter = lastResponse?.headers?.get('Retry-After');
            const waitMs = retryAfter ? parseInt(retryAfter) * 1000 : (500 * Math.pow(2, attempt - 1));
            await new Promise(r => setTimeout(r, waitMs));
          }
          lastResponse = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `ApiKey ${env.OPEN_SANCTIONS_KEY}`,
            },
            body: JSON.stringify(payload),
          });
          if (lastResponse.status !== 429) break;
        }

        const data = await lastResponse.json();
        return new Response(JSON.stringify(data), {
          status: lastResponse.status,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      // Default: route to Anthropic
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      return new Response(JSON.stringify(data), {
        status: response.status,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  }
};
