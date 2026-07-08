"""Default Jinja XML templates for Immowelt/OpenImmo export.

Copy-paste these into the Integration Source xml_template field after
enabling 'Use Jinja Template'.

Available context variables in templates:
    doc         - The Property document (full Frappe document)
    mapped      - Flat XML-path-to-value dict from export_mapper
    source      - Integration Source document
    frappe      - Full frappe object (for frappe.get_doc, frappe.db, etc.)

Available custom methods (registered via hooks.py):
    get_document(doctype, name)     - Fetch a linked document
    get_value(doctype, name, field) - Fetch a single field value
    format_immowelt_date(value)     - Convert YYYY-MM-DD to MM-YYYY
    format_decimal(value)           - Convert 189,0 to 189.0

Built-in Frappe Jinja globals:
    frappe.utils.nowdate, frappe.utils.now_datetime, frappe.utils.cint,
    frappe.utils.flt, frappe.utils.cstr, etc.
"""

# ---------------------------------------------------------------------------
# IMMOWELT EXPOSE TEMPLATE (OpenImmo XML 1.2.7 compliant)
# ---------------------------------------------------------------------------
# Usage: Set record_packaging = "Separate XML per Record"
#        Loop through all_records in batch mode or use doc in single mode.
# ---------------------------------------------------------------------------

IMMOWELT_EXPOSE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<expose>
    <address>
        <company>{{ source.provider_name or "" }}</company>
    </address>

    <estate
        id="{{ doc.name }}"
        guid="{{ doc.name }}"
        onlineid="{{ doc.custom_unit_id or doc.name }}"
        type-id="{{ mapped.get('estate.type_id') or '' }}"
        type-description="{{ mapped.get('estate.type_description') or '' }}"
        salestype="{{ mapped.get('estate.salestype') or '' }}"
        category-id="{{ mapped.get('estate.category_id', '') }}"
        category-description="{{ mapped.get('estate.category_description', '') }}">

        {# --- Basic Info Items --- #}
        {% for item_id, xml_path in [
            ("ReferenceNumber", "verwaltung_techn.objektnr_intern"),
            ("OnlineID", "verwaltung_techn.objektnr_extern"),
            ("Description", "freitexte.objekttitel"),
            ("LocationStreet", "geo.strasse"),
            ("LocationZip", "geo.plz"),
            ("LocationCity", "geo.ort"),
            ("LocationCountry", "geo.land"),
            ("Price", "preise.kaltmiete"),
            ("AdditionalCosts", "preise.nebenkosten"),
            ("PriceWarmmiete", "preise.warmmiete"),
            ("Baujahr", "zustand_angaben.baujahr"),
            ("Bezugsfrei", "verwaltung_techn.verfuegbar_ab"),
            ("AreaLiving", "flaechen.wohnflaeche"),
            ("AreaLand", "flaechen.grundstuecksflaeche"),
            ("Rooms", "flaechen.anzahl_zimmer"),
            ("Info1", "freitexte.objektbeschreibung"),
            ("Info2", "freitexte.lage"),
            ("Info3", "freitexte.ausstatt_beschr"),
        ] %}
            {% set val = mapped.get(xml_path) %}
            {% if val not in [none, ""] %}
            <item id="{{ item_id }}">
                <title>{{ item_id }}</title>
                <description>{{ val }}</description>
            </item>
            {% endif %}
        {% endfor %}

        {# --- Energy Certificate (linked document) --- #}
        {% if doc.custom_energy_certificate %}
            {% set cert = frappe.get_doc("Energy Certificate Link", doc.custom_energy_certificate) %}
            {% if cert %}
            <energyperformance
                visible="true"
                EnergiePassArt="{{ cert.energiepass_art or '' }}"
                EnergiePassWert="{{ cert.energiepass_kennwert | format_decimal if cert.energiepass_kennwert else '' }}"
                EnergiePassWertKlasse="{{ cert.energieeffizienzklasse or '' }}"
                EnergiePassInclWasser="{{ cert.mitwarmwasser or '' }}" />
            {% endif %}
        {% endif %}

        {# --- Image Gallery with hero image logic --- #}
        {% if doc.custom_image_gallery %}
        <images>
            {% for img in doc.custom_image_gallery %}
                {% if loop.first %}
            <thumbnail>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</thumbnail>
                {% endif %}
            <image id="{{ loop.index0 }}">
                <source>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</source>
                <description>Bild {{ loop.index }}</description>
                <source_thumbnail>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</source_thumbnail>
                <source_XXL>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</source_XXL>
            </image>
            {% endfor %}
        </images>
        {% endif %}

        {# --- Attachments --- #}
        {% if doc.custom_image_gallery %}
        <attachments>
            {% for img in doc.custom_image_gallery %}
            <Document id="{{ loop.index0 }}">
                <source>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</source>
                <description>Bild {{ loop.index }}</description>
            </Document>
            {% endfor %}
        </attachments>
        {% endif %}

        {# --- Geo Data --- #}
        {% if doc.custom_latitude or doc.custom_longitude %}
        <GeoData>
            {% if doc.custom_latitude %}<breitengrad>{{ doc.custom_latitude }}</breitengrad>{% endif %}
            {% if doc.custom_longitude %}<laengengrad>{{ doc.custom_longitude }}</laengengrad>{% endif %}
        </GeoData>
        {% endif %}
    </estate>
</expose>"""


# ---------------------------------------------------------------------------
# BATCH MODE TEMPLATE (multiple properties in one XML)
# ---------------------------------------------------------------------------
# Usage: Set record_packaging = "Single XML for All Records"
#        Template receives all_records = [{"doc": ..., "mapped": ...}, ...]
# ---------------------------------------------------------------------------

IMMOWELT_BATCH_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<exposes>
{% for rec in all_records %}
    {% set doc = rec.doc %}
    {% set mapped = rec.mapped %}
    <expose>
        <address>
            <company>{{ source.provider_name or "" }}</company>
        </address>
        <estate id="{{ doc.name }}" guid="{{ doc.name }}">
            {% if doc.custom_energy_certificate %}
                {% set cert = frappe.get_doc("Energy Certificate Link", doc.custom_energy_certificate) %}
                {% if cert %}
                <energyperformance visible="true"
                    EnergiePassWert="{{ cert.energiepass_kennwert | format_decimal if cert.energiepass_kennwert else '' }}" />
                {% endif %}
            {% endif %}

            {% if doc.custom_image_gallery %}
            <images>
                {% for img in doc.custom_image_gallery %}
                <image id="{{ loop.index0 }}">
                    <source>{{ source.base_media_url or frappe.utils.get_url() }}/{{ img.picture }}</source>
                </image>
                {% endfor %}
            </images>
            {% endif %}
        </estate>
    </expose>
{% endfor %}
</exposes>"""


# ---------------------------------------------------------------------------
# OPENIMMO JINJA TEMPLATE (OpenImmo XML 1.2.7 XSD compliant)
# ---------------------------------------------------------------------------
# Usage: Supports both "Separate XML per Record" and "Single XML for All Records".
#        Paste this template into the xml_template field of Integration Source.
# ---------------------------------------------------------------------------

OPENIMMO_JINJA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<openimmo>
    <uebertragung art="ONLINE"
                  umfang="{{ source.transfer_scope or '' }}"
                  modus="{{ source.transfer_mode or '' }}"
                  version="1.2.7"
                  sendersoftware="OIGEN"
                  senderversion="1.0"
                  timestamp="{{ frappe.utils.now_datetime().strftime('%Y-%m-%dT%H:%M:%S') }}"/>
    <anbieter>
        <anbieternr>{{ source.anbieter_id or '' }}</anbieternr>
        <firma>{{ source.provider_name or '' }}</firma>
        <openimmo_anid>{{ source.openimmo_anid or '' }}</openimmo_anid>

        {%- if all_records -%}
            {%- set records = all_records -%}
        {%- else -%}
            {%- set records = [{'doc': doc, 'mapped': mapped}] -%}
        {%- endif -%}

        {%- for rec in records -%}
            {%- set doc = rec.doc -%}
            {%- set mapped = rec.mapped -%}
            <immobilie>
                <objektkategorie>
                    <nutzungsart
                        WOHNEN="{{ 'true' if mapped.get('objektkategorie.nutzungsart@WOHNEN') else 'false' }}"
                        GEWERBE="{{ 'true' if mapped.get('objektkategorie.nutzungsart@GEWERBE') else 'false' }}"
                        ANLAGE="{{ 'true' if mapped.get('objektkategorie.nutzungsart@ANLAGE') else 'false' }}"
                        WAZ="{{ 'true' if mapped.get('objektkategorie.nutzungsart@WAZ') else 'false' }}" />
                    <vermarktungsart
                        KAUF="{{ 'true' if mapped.get('objektkategorie.vermarktungsart@KAUF') else 'false' }}"
                        MIETE_PACHT="{{ 'true' if mapped.get('objektkategorie.vermarktungsart@MIETE_PACHT') else 'false' }}"
                        {%- if mapped.get('objektkategorie.vermarktungsart@ERBPACHT') is not none %} ERBPACHT="{{ 'true' if mapped.get('objektkategorie.vermarktungsart@ERBPACHT') else 'false' }}"{% endif -%}
                        {%- if mapped.get('objektkategorie.vermarktungsart@LEASING') is not none %} LEASING="{{ 'true' if mapped.get('objektkategorie.vermarktungsart@LEASING') else 'false' }}"{% endif -%} />
                    <objektart>
                        {%- set ns = namespace(tag="", attrs="") -%}
                        {%- for key, val in mapped.items() if key.startswith("objektkategorie.objektart.") -%}
                            {%- if "@" in key -%}
                                {%- set tag_and_attr = key.replace("objektkategorie.objektart.", "") -%}
                                {%- set tag = tag_and_attr.split("@")[0] -%}
                                {%- set attr_name = tag_and_attr.split("@")[1] -%}
                                {%- set ns.tag = tag -%}
                                {%- set ns.attrs = ns.attrs ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                            {%- else -%}
                                {%- set ns.tag = key.replace("objektkategorie.objektart.", "") -%}
                            {%- endif -%}
                        {%- endfor -%}
                        {%- if ns.tag -%}
                            <{{ ns.tag }}{{ ns.attrs }}/>
                        {%- else -%}
                            <sonstige />
                        {%- endif -%}
                    </objektart>
                    {%- for key, val in mapped.items() if key.startswith("objektkategorie.user_defined_simplefield") and "@feldname" in key -%}
                    <user_defined_simplefield feldname="{{ val }}"/>
                    {%- endfor -%}
                </objektkategorie>

                <geo>
                    {%- if mapped.get('geo.plz') %}<plz>{{ mapped.get('geo.plz') }}</plz>{% endif -%}
                    {%- if mapped.get('geo.ort') %}<ort>{{ mapped.get('geo.ort') }}</ort>{% endif -%}
                    {%- if mapped.get('geo.geokoordinaten@breitengrad') or mapped.get('geo.geokoordinaten@laengengrad') -%}
                    <geokoordinaten breitengrad="{{ mapped.get('geo.geokoordinaten@breitengrad') }}" laengengrad="{{ mapped.get('geo.geokoordinaten@laengengrad') }}"/>
                    {%- endif -%}
                    {%- if mapped.get('geo.strasse') %}<strasse>{{ mapped.get('geo.strasse') }}</strasse>{% endif -%}
                    {%- if mapped.get('geo.hausnummer') %}<hausnummer>{{ mapped.get('geo.hausnummer') }}</hausnummer>{% endif -%}
                    {%- if mapped.get('geo.bundesland') %}<bundesland>{{ mapped.get('geo.bundesland') }}</bundesland>{% endif -%}
                    <land iso_land="{{ mapped.get('geo.land@iso_land') or '' }}"/>
                    {%- if mapped.get('geo.gemeindecode') %}<gemeindecode>{{ mapped.get('geo.gemeindecode') }}</gemeindecode>{% endif -%}
                    {%- if mapped.get('geo.flur') %}<flur>{{ mapped.get('geo.flur') }}</flur>{% endif -%}
                    {%- if mapped.get('geo.flurstueck') %}<flurstueck>{{ mapped.get('geo.flurstueck') }}</flurstueck>{% endif -%}
                    {%- if mapped.get('geo.gemarkung') %}<gemarkung>{{ mapped.get('geo.gemarkung') }}</gemarkung>{% endif -%}
                    {%- if mapped.get('geo.etage') is not none and mapped.get('geo.etage') != "" %}<etage>{{ mapped.get('geo.etage') }}</etage>{% endif -%}
                    {%- if mapped.get('geo.anzahl_etagen') is not none and mapped.get('geo.anzahl_etagen') != "" %}<anzahl_etagen>{{ mapped.get('geo.anzahl_etagen') }}</anzahl_etagen>{% endif -%}
                    {%- if mapped.get('geo.lage_im_bau') %}<lage_im_bau>{{ mapped.get('geo.lage_im_bau') }}</lage_im_bau>{% endif -%}
                    {%- if mapped.get('geo.wohnungsnr') %}<wohnungsnr>{{ mapped.get('geo.wohnungsnr') }}</wohnungsnr>{% endif -%}
                    {%- if mapped.get('geo.lage_gebiet') %}<lage_gebiet>{{ mapped.get('geo.lage_gebiet') }}</lage_gebiet>{% endif -%}
                    {%- if mapped.get('geo.regionaler_zusatz') %}<regionaler_zusatz>{{ mapped.get('geo.regionaler_zusatz') }}</regionaler_zusatz>{% endif -%}
                    {%- if mapped.get('geo.karten_makro') %}<karten_makro>{{ mapped.get('geo.karten_makro') }}</karten_makro>{% endif -%}
                    {%- if mapped.get('geo.karten_mikro') %}<karten_mikro>{{ mapped.get('geo.karten_mikro') }}</karten_mikro>{% endif -%}
                </geo>

                {%- set has_kontakt = mapped.get('kontaktperson.email_zentrale') or mapped.get('kontaktperson.email_direkt') or mapped.get('kontaktperson.tel_zentrale') or mapped.get('kontaktperson.tel_handy') or mapped.get('kontaktperson.name') -%}
                {%- if has_kontakt -%}
                <kontaktperson>
                    {%- if mapped.get('kontaktperson.email_zentrale') %}<email_zentrale>{{ mapped.get('kontaktperson.email_zentrale') }}</email_zentrale>{% endif -%}
                    {%- if mapped.get('kontaktperson.email_direkt') %}<email_direkt>{{ mapped.get('kontaktperson.email_direkt') }}</email_direkt>{% endif -%}
                    {%- if mapped.get('kontaktperson.tel_zentrale') %}<tel_zentrale>{{ mapped.get('kontaktperson.tel_zentrale') }}</tel_zentrale>{% endif -%}
                    {%- if mapped.get('kontaktperson.tel_durchw') %}<tel_durchw>{{ mapped.get('kontaktperson.tel_durchw') }}</tel_durchw>{% endif -%}
                    {%- if mapped.get('kontaktperson.tel_fax') %}<tel_fax>{{ mapped.get('kontaktperson.tel_fax') }}</tel_fax>{% endif -%}
                    {%- if mapped.get('kontaktperson.tel_handy') %}<tel_handy>{{ mapped.get('kontaktperson.tel_handy') }}</tel_handy>{% endif -%}
                    <name>{{ mapped.get('kontaktperson.name') or '' }}</name>
                    {%- if mapped.get('kontaktperson.vorname') %}<vorname>{{ mapped.get('kontaktperson.vorname') }}</vorname>{% endif -%}
                    {%- if mapped.get('kontaktperson.titel') %}<titel>{{ mapped.get('kontaktperson.titel') }}</titel>{% endif -%}
                    {%- if mapped.get('kontaktperson.anrede') %}<anrede>{{ mapped.get('kontaktperson.anrede') }}</anrede>{% endif -%}
                </kontaktperson>
                {%- endif -%}

                {%- if mapped.get('weitere_adresse.name') or doc.get('custom_weitere_adresse_name') -%}
                <weitere_adresse adressart="{{ mapped.get('weitere_adresse@adressart') or '' }}">
                    <name>{{ mapped.get('weitere_adresse.name') or doc.get('custom_weitere_adresse_name') }}</name>
                </weitere_adresse>
                {%- endif -%}

                {%- set has_preise = mapped.get('preise.kaltmiete') is not none or mapped.get('preise.kaufpreis') is not none or mapped.get('preise.warmmiete') is not none -%}
                {%- if has_preise -%}
                <preise>
                    {%- if mapped.get('preise.kaufpreis') is not none %}<kaufpreis>{{ mapped.get('preise.kaufpreis') }}</kaufpreis>{% endif -%}
                    {%- if mapped.get('preise.kaltmiete') is not none %}<kaltmiete>{{ mapped.get('preise.kaltmiete') }}</kaltmiete>{% endif -%}
                    {%- if mapped.get('preise.warmmiete') is not none %}<warmmiete>{{ mapped.get('preise.warmmiete') }}</warmmiete>{% endif -%}
                    {%- if mapped.get('preise.nebenkosten') is not none %}<nebenkosten>{{ mapped.get('preise.nebenkosten') }}</nebenkosten>{% endif -%}
                    {%- if mapped.get('preise.heizkosten') is not none %}<heizkosten>{{ mapped.get('preise.heizkosten') }}</heizkosten>{% endif -%}
                    {%- if mapped.get('preise.zzg_mehrwertsteuer') is not none -%}
                    <zzg_mehrwertsteuer>{{ 'true' if mapped.get('preise.zzg_mehrwertsteuer') in [true, 'true', 1, '1'] else 'false' }}</zzg_mehrwertsteuer>
                    {%- endif -%}
                    {%- if mapped.get('preise.provisionspflichtig') is not none -%}
                    <provisionspflichtig>{{ 'true' if mapped.get('preise.provisionspflichtig') in [true, 'true', 1, '1'] else 'false' }}</provisionspflichtig>
                    {%- endif -%}
                    <waehrung iso_waehrung="{{ mapped.get('preise.waehrung@iso_waehrung') or '' }}"/>
                    {%- if mapped.get('preise.kaution') is not none %}<kaution>{{ mapped.get('preise.kaution') }}</kaution>{% endif -%}
                    {%- if mapped.get('preise.kaution_text') %}<kaution_text>{{ mapped.get('preise.kaution_text') }}</kaution_text>{% endif -%}
                </preise>
                {%- endif -%}

                {%- set has_flaechen = mapped.get('flaechen.wohnflaeche') is not none or mapped.get('flaechen.nutzflaeche') is not none or mapped.get('flaechen.gesamtflaeche') is not none or mapped.get('flaechen.anzahl_zimmer') is not none -%}
                {%- if has_flaechen -%}
                <flaechen>
                    {%- if mapped.get('flaechen.wohnflaeche') is not none %}<wohnflaeche>{{ mapped.get('flaechen.wohnflaeche') }}</wohnflaeche>{% endif -%}
                    {%- if mapped.get('flaechen.nutzflaeche') is not none %}<nutzflaeche>{{ mapped.get('flaechen.nutzflaeche') }}</nutzflaeche>{% endif -%}
                    {%- if mapped.get('flaechen.gesamtflaeche') is not none %}<gesamtflaeche>{{ mapped.get('flaechen.gesamtflaeche') }}</gesamtflaeche>{% endif -%}
                    {%- if mapped.get('flaechen.anzahl_zimmer') is not none %}<anzahl_zimmer>{{ mapped.get('flaechen.anzahl_zimmer') }}</anzahl_zimmer>{% endif -%}
                    {%- if mapped.get('flaechen.anzahl_schlafzimmer') is not none %}<anzahl_schlafzimmer>{{ mapped.get('flaechen.anzahl_schlafzimmer') }}</anzahl_schlafzimmer>{% endif -%}
                    {%- if mapped.get('flaechen.anzahl_badezimmer') is not none %}<anzahl_badezimmer>{{ mapped.get('flaechen.anzahl_badezimmer') }}</anzahl_badezimmer>{% endif -%}
                    {%- if mapped.get('flaechen.anzahl_balkone') is not none %}<anzahl_balkone>{{ mapped.get('flaechen.anzahl_balkone') }}</anzahl_balkone>{% endif -%}
                </flaechen>
                {%- endif -%}

                {%- set heiz_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("ausstattung.heizungsart@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set heiz_attrs.val = heiz_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}
                
                {%- set bef_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("ausstattung.befeuerung@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set bef_attrs.val = bef_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}

                {%- set fahr_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("ausstattung.fahrstuhl@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set fahr_attrs.val = fahr_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}

                {%- set moeb_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("ausstattung.moebliert@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set moeb_attrs.val = moeb_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}

                {%- set bb_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("ausstattung.breitband_zugang@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set bb_attrs.val = bb_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}

                {%- set has_ausstattung = mapped.get('ausstattung.ausstatt_kategorie') or heiz_attrs.val or bef_attrs.val or fahr_attrs.val or moeb_attrs.val or bb_attrs.val or 'ausstattung.moebliert' in mapped -%}
                {%- if has_ausstattung -%}
                <ausstattung>
                    {%- if mapped.get('ausstattung.ausstatt_kategorie') -%}
                    <ausstatt_kategorie>{{ mapped.get('ausstattung.ausstatt_kategorie') }}</ausstatt_kategorie>
                    {%- endif -%}
                    {%- if heiz_attrs.val -%}
                    <heizungsart{{ heiz_attrs.val }}/>
                    {%- endif -%}
                    {%- if bef_attrs.val -%}
                    <befeuerung{{ bef_attrs.val }}/>
                    {%- endif -%}
                    {%- if fahr_attrs.val -%}
                    <fahrstuhl{{ fahr_attrs.val }}/>
                    {%- endif -%}
                    {%- if moeb_attrs.val or 'ausstattung.moebliert' in mapped -%}
                    <moebliert{{ moeb_attrs.val }}/>
                    {%- endif -%}
                    {%- if bb_attrs.val -%}
                    <breitband_zugang{{ bb_attrs.val }}/>
                    {%- endif -%}
                </ausstattung>
                {%- endif -%}

                {%- set ep_attrs = namespace(val="") -%}
                {%- for key, val in mapped.items() if key.startswith("zustand_angaben.energiepass@") -%}
                    {%- set attr_name = key.split("@")[1] -%}
                    {%- set ep_attrs.val = ep_attrs.val ~ ' ' ~ attr_name ~ '="' ~ val ~ '"' -%}
                {%- endfor -%}
                {%- set has_ep = ep_attrs.val or mapped.get('zustand_angaben.energiepass.mitwarmwasser') is not none or doc.custom_energy_certificate -%}
                {%- set has_zustand_angaben = mapped.get('zustand_angaben.baujahr') or mapped.get('zustand_angaben.zustand@zustand_art') or mapped.get('zustand_angaben.zustand_art') or has_ep -%}
                {%- if has_zustand_angaben -%}
                <zustand_angaben>
                    {%- if mapped.get('zustand_angaben.baujahr') -%}
                    <baujahr>{{ mapped.get('zustand_angaben.baujahr') }}</baujahr>
                    {%- endif -%}
                    {%- if mapped.get('zustand_angaben.zustand@zustand_art') or mapped.get('zustand_angaben.zustand_art') -%}
                    <zustand zustand_art="{{ mapped.get('zustand_angaben.zustand@zustand_art') or mapped.get('zustand_angaben.zustand_art') }}"/>
                    {%- endif -%}
                    {%- if has_ep -%}
                    <energiepass{{ ep_attrs.val }}>
                        {%- set mitwarmwasser = mapped.get('zustand_angaben.energiepass.mitwarmwasser') -%}
                        {%- if mitwarmwasser is not none -%}
                        <mitwarmwasser>{{ 'true' if mitwarmwasser in [true, 'true', 1, '1'] else 'false' }}</mitwarmwasser>
                        {%- endif -%}
                    </energiepass>
                    {%- endif -%}
                </zustand_angaben>
                {%- endif -%}

                {%- set found_bewertung = namespace(has_any=false) -%}
                {%- for key in mapped.keys() if key.startswith("bewertung.feld.") -%}
                    {%- set found_bewertung.has_any = true -%}
                {%- endfor -%}
                {%- if found_bewertung.has_any -%}
                <bewertung>
                    {%- set indices = [] -%}
                    {%- for key in mapped.keys() if key.startswith("bewertung.feld.") -%}
                        {%- set parts = key.split(".") -%}
                        {%- if parts|length > 2 and parts[2].isdigit() and parts[2]|int not in indices -%}
                            {%- set _ = indices.append(parts[2]|int) -%}
                        {%- endif -%}
                    {%- endfor -%}
                    {%- for idx in indices|sort -%}
                        {%- set name_path = "bewertung.feld." ~ idx ~ ".name" -%}
                        {%- set wert_path = "bewertung.feld." ~ idx ~ ".wert" -%}
                        <feld>
                            <name>{{ mapped.get(name_path) }}</name>
                            <wert>{{ mapped.get(wert_path) }}</wert>
                        </feld>
                    {%- endfor -%}
                </bewertung>
                {%- elif doc.custom_bewertungen or doc.get('bewertung') -%}
                <bewertung>
                    {%- set items = doc.custom_bewertungen or doc.get('bewertung') or [] -%}
                    {%- for item in items -%}
                    <feld>
                        <name>{{ item.name or item.get('name') }}</name>
                        <wert>{{ item.wert or item.get('wert') }}</wert>
                    </feld>
                    {%- endfor -%}
                </bewertung>
                {%- endif -%}

                {%- set has_freitexte = mapped.get('freitexte.objekttitel') or mapped.get('freitexte.dreizeiler') or mapped.get('freitexte.lage') or mapped.get('freitexte.ausstatt_beschr') or mapped.get('freitexte.objektbeschreibung') or mapped.get('freitexte.sonstige_angaben') -%}
                {%- if has_freitexte -%}
                <freitexte>
                    {%- if mapped.get('freitexte.objekttitel') -%}
                    <objekttitel>{{ mapped.get('freitexte.objekttitel') }}</objekttitel>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.dreizeiler') -%}
                    <dreizeiler>{{ mapped.get('freitexte.dreizeiler') }}</dreizeiler>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.lage') -%}
                    <lage>{{ mapped.get('freitexte.lage') }}</lage>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.ausstatt_beschr') -%}
                    <ausstatt_beschr>{{ mapped.get('freitexte.ausstatt_beschr') }}</ausstatt_beschr>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.objektbeschreibung') -%}
                    <objektbeschreibung>{{ mapped.get('freitexte.objektbeschreibung') }}</objektbeschreibung>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.sonstige_angaben') -%}
                    <sonstige_angaben>{{ mapped.get('freitexte.sonstige_angaben') }}</sonstige_angaben>
                    {%- endif -%}
                    {%- if mapped.get('freitexte.objekt_text') is not none or 'freitexte.objekt_text' in mapped or mapped.get('freitexte.objekt_text@lang') -%}
                    <objekt_text lang="{{ mapped.get('freitexte.objekt_text@lang') or '' }}"/>
                    {%- endif -%}
                </freitexte>
                {%- endif -%}

                {%- set found_anhaenge = namespace(has_any=false) -%}
                {%- for key in mapped.keys() if key.startswith("anhaenge.anhang.") -%}
                    {%- set found_anhaenge.has_any = true -%}
                {%- endfor -%}
                {%- if found_anhaenge.has_any -%}
                <anhaenge>
                    {%- set indices = [] -%}
                    {%- for key in mapped.keys() if key.startswith("anhaenge.anhang.") -%}
                        {%- set parts = key.split(".") -%}
                        {%- if parts|length > 2 and parts[2].isdigit() and parts[2]|int not in indices -%}
                            {%- set _ = indices.append(parts[2]|int) -%}
                        {%- endif -%}
                    {%- endfor -%}
                    {%- for idx in indices|sort -%}
                        {%- set pfad_path = "anhaenge.anhang." ~ idx ~ ".daten.pfad" -%}
                        {%- set format_path = "anhaenge.anhang." ~ idx ~ ".format" -%}
                        {%- set title_path = "anhaenge.anhang." ~ idx ~ ".anhangtitel" -%}
                        {%- set loc_path = "anhaenge.anhang." ~ idx ~ "@location" -%}
                        {%- set grp_path = "anhaenge.anhang." ~ idx ~ "@gruppe" -%}
                        {%- set pfad_val = mapped.get(pfad_path) -%}
                        {%- if pfad_val -%}
                        <anhang location="{{ mapped.get(loc_path) or '' }}"{% if mapped.get(grp_path) %} gruppe="{{ mapped.get(grp_path) }}"{% endif %}>
                            {%- if mapped.get(title_path) -%}
                            <anhangtitel>{{ mapped.get(title_path) }}</anhangtitel>
                            {%- endif -%}
                            <format>{{ mapped.get(format_path) or '' }}</format>
                            <daten>
                                <pfad>{{ pfad_val }}</pfad>
                            </daten>
                        </anhang>
                        {%- endif -%}
                    {%- endfor -%}
                </anhaenge>
                {%- elif doc.custom_image_gallery -%}
                <anhaenge>
                    {%- for row in doc.custom_image_gallery -%}
                        {%- set img_path = row.get("picture") -%}
                        {%- if img_path -%}
                            {%- set ext = img_path.split('.')[-1].upper() if '.' in img_path else 'JPEG' -%}
                            {%- set format_map = {'JPG': 'JPEG', 'JPEG': 'JPEG', 'PNG': 'PNG', 'GIF': 'GIF', 'WEBP': 'JPEG'} -%}
                            {%- set fmt = format_map.get(ext, 'JPEG') -%}
                            {%- set base_media_url = source.base_media_url or frappe.utils.get_url() -%}
                            {%- set full_path = img_path if img_path.startswith(('http://', 'https://')) else (base_media_url.rstrip('/') ~ '/' ~ img_path.lstrip('/')) -%}
                            <anhang location="EXTERN" gruppe="{{ 'TITELBILD' if loop.first else 'INNENANSICHTEN' }}">
                                <format>{{ fmt }}</format>
                                <daten>
                                    <pfad>{{ full_path }}</pfad>
                                </daten>
                            </anhang>
                        {%- endif -%}
                    {%- endfor -%}
                </anhaenge>
                {%- endif -%}

                {%- set has_verwaltung_objekt = mapped.get('verwaltung_objekt.verfuegbar_ab') or mapped.get('verwaltung_objekt.haustiere') is not none or mapped.get('verwaltung_objekt.denkmalgeschuetzt') is not none -%}
                {%- if has_verwaltung_objekt -%}
                <verwaltung_objekt>
                    {%- if mapped.get('verwaltung_objekt.verfuegbar_ab') -%}
                    <verfuegbar_ab>{{ mapped.get('verwaltung_objekt.verfuegbar_ab') }}</verfuegbar_ab>
                    {%- endif -%}
                    {%- if mapped.get('verwaltung_objekt.haustiere') is not none -%}
                    <haustiere>{{ 'true' if mapped.get('verwaltung_objekt.haustiere') in [true, 'true', 1, '1'] else 'false' }}</haustiere>
                    {%- endif -%}
                    {%- if mapped.get('verwaltung_objekt.denkmalgeschuetzt') is not none -%}
                    <denkmalgeschuetzt>{{ 'true' if mapped.get('verwaltung_objekt.denkmalgeschuetzt') in [true, 'true', 1, '1'] else 'false' }}</denkmalgeschuetzt>
                    {%- endif -%}
                </verwaltung_objekt>
                {%- endif -%}

                <verwaltung_techn>
                    <objektnr_intern>{{ mapped.get('verwaltung_techn.objektnr_intern') or '' }}</objektnr_intern>
                    <objektnr_extern>{{ mapped.get('verwaltung_techn.objektnr_extern') or '' }}</objektnr_extern>
                    <aktion aktionart="{{ mapped.get('verwaltung_techn.aktion@aktionart') or mapped.get('verwaltung_techn.aktion') or source.transfer_mode or '' }}"/>
                    <openimmo_obid>{{ mapped.get('verwaltung_techn.openimmo_obid') or '' }}</openimmo_obid>
                    <stand_vom>{{ mapped.get('verwaltung_techn.stand_vom') or '' }}</stand_vom>
                </verwaltung_techn>
            </immobilie>
        {%- endfor -%}
    </anbieter>
</openimmo>
"""

