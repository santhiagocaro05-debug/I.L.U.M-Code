import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.46.1";
import { decode } from "https://deno.land/std@0.177.0/encoding/base64.ts";

function hexString(buffer: ArrayBuffer) {
  const byteArray = new Uint8Array(buffer);
  const hexCodes = [...byteArray].map(value => {
    const hexCode = value.toString(16);
    const paddedHexCode = hexCode.padStart(2, '0');
    return paddedHexCode;
  });
  return hexCodes.join('');
}

function importPrivateKey(pem: string) {
  const pemHeader = "-----BEGIN PRIVATE KEY-----";
  const pemFooter = "-----END PRIVATE KEY-----";
  
  let pemContents = pem;
  // Replace literal '\n' (backslash + 'n') with spaces
  pemContents = pemContents.replace(/\\n/g, ' ');
  // Replace actual newlines with spaces
  pemContents = pemContents.replace(/\n/g, ' ');
  
  const startIdx = pemContents.indexOf(pemHeader);
  const endIdx = pemContents.indexOf(pemFooter);
  
  if (startIdx === -1 || endIdx === -1) {
    throw new Error("Invalid PEM format: header or footer not found");
  }
  
  pemContents = pemContents.substring(startIdx + pemHeader.length, endIdx);
  // Remove all spaces, tabs, newlines, and other whitespace
  pemContents = pemContents.replace(/\s/g, '');

  const binaryDer = decode(pemContents);

  return crypto.subtle.importKey(
    "pkcs8",
    binaryDer.buffer,
    {
      name: "ECDSA",
      namedCurve: "P-256",
    },
    true,
    ["sign"]
  );
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const { p_license_key, p_hwid } = await req.json();

    if (!p_license_key || !p_hwid) {
      return new Response(
        JSON.stringify({ success: false, message: "Missing p_license_key or p_hwid" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    // Create a Supabase client with the Auth context of the logged in user.
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    const supabase = createClient(supabaseUrl, supabaseKey);

    // 1. Validate License Exists
    const { data: licenses, error } = await supabase
      .from('licenses')
      .select('*')
      .eq('key', p_license_key)
      .limit(1);

    if (error || !licenses || licenses.length === 0) {
      return new Response(
        JSON.stringify({ success: false, message: "Licencia no encontrada o inválida." }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const license = licenses[0];

    // 2. Validate is_active
    if (!license.is_active) {
      return new Response(
        JSON.stringify({ success: false, message: "La licencia ha sido bloqueada por el administrador." }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    // 3. Check HWID
    let hwidToReturn = license.registered_hwid;

    if (!license.registered_hwid) {
      // First time use, register the HWID
      const { error: updateError } = await supabase
        .from('licenses')
        .update({ registered_hwid: p_hwid })
        .eq('key', p_license_key);

      if (updateError) throw updateError;
      hwidToReturn = p_hwid;
    } else if (license.registered_hwid !== p_hwid) {
      // Hardware mismatch
      return new Response(
        JSON.stringify({ success: false, message: "Hardware no coincide. La licencia ya está registrada en otro equipo." }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
      );
    }

    const privateKeyPem = Deno.env.get('ECDSA_PRIVATE_KEY');
    if (!privateKeyPem) {
        throw new Error("ECDSA_PRIVATE_KEY missing from Edge Function Secrets");
    }

    const success_str = "True";
    const email_str = (license.email || "").trim().toLowerCase();
    const hwid_str = (hwidToReturn || "").trim();
    const msg_payload = `success:${success_str}|email:${email_str}|hwid:${hwid_str}`;

    const importedKey = await importPrivateKey(privateKeyPem);
    const signatureBuffer = await crypto.subtle.sign(
      {
        name: "ECDSA",
        hash: { name: "SHA-256" },
      },
      importedKey,
      new TextEncoder().encode(msg_payload)
    );

    const signatureHex = hexString(signatureBuffer);

    return new Response(
      JSON.stringify({
        success: true,
        message: "Licencia validada y registrada correctamente.",
        email: license.email,
        hwid: hwidToReturn,
        signature: signatureHex
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
    );

  } catch (error) {
    return new Response(
      JSON.stringify({ success: false, message: "Internal server error: " + error.message }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});
