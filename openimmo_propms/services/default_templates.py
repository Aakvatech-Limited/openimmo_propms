"""Default Jinja XML templates for OpenImmo export."""

OPENIMMO_JINJA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!--    
	OpenImmo $VERSION: 1.2.7
	Direct Jinja template mapping all Property fields directly (no fallback values).
	Resolves Property Type and Nutzungsart from linked DocType dynamically.
-->
<openimmo>
    <uebertragung art="ONLINE" 
                  umfang="{{ source.transfer_scope }}" 
                  modus="{{ source.transfer_mode }}" 
                  version="1.2.7" 
                  sendersoftware="OIGEN" 
                  senderversion="1.0" 
                  timestamp="{{ frappe.utils.now_datetime().strftime('%Y-%m-%dT%H:%M:%S') }}"
                  {%- if source.regi_id %} regi_id="{{ source.regi_id }}"{% endif -%}/>
    <anbieter>
        <anbieternr>{{ source.anbieter_id }}</anbieternr>
        <firma>{{ source.provider_name }}</firma>
        <openimmo_anid>{{ source.openimmo_anid }}</openimmo_anid>

        {# --- Setup Records List for both Single & Batch packaging --- #}
        {%- if all_records -%}
            {%- set records = all_records -%}
        {%- else -%}
            {%- set records = [{'doc': doc}] -%}
        {%- endif -%}

        {%- for rec in records -%}
            {%- set doc = rec.doc -%}
            <immobilie>
                <objektkategorie>
                    {# --- Setup namespace to fetch usage attributes dynamically --- #}
                    {%- set ns_na = namespace(wohnen="false", gewerbe="false", anlage="false", waz="false") -%}
                    {%- if doc.custom_property_type -%}
                        {%- set prop_type = frappe.get_doc("Property Type", doc.custom_property_type) -%}
                        {%- if prop_type -%}
                            {%- set ns_na.wohnen = "true" if prop_type.use_residential else "false" -%}
                            {%- set ns_na.gewerbe = "true" if prop_type.use_commercial else "false" -%}
                            {%- set ns_na.anlage = "true" if prop_type.use_investment else "false" -%}
                            {%- set ns_na.waz = "true" if prop_type.use_mixed else "false" -%}
                        {%- endif -%}
                    {%- endif -%}
                    <nutzungsart WOHNEN="{{ ns_na.wohnen }}" GEWERBE="{{ ns_na.gewerbe }}" ANLAGE="{{ ns_na.anlage }}" WAZ="{{ ns_na.waz }}"/>
                    <vermarktungsart KAUF="false" MIETE_PACHT="true" ERBPACHT="false" LEASING="false"/>
                    
                    <objektart>
                        {%- if doc.custom_property_type -%}
                            {%- set prop_type = frappe.get_doc("Property Type", doc.custom_property_type) -%}
                            {%- if prop_type -%}
                                {%- set objektart = prop_type.openimmo_objektart -%}
                                {%- set attribute = prop_type.openimmo_attribute -%}
                                {%- set value = prop_type.openimmo_value -%}
                                {%- if objektart -%}
                                    <{{ objektart }}{% if attribute and value %} {{ attribute }}="{{ value | upper }}"{% endif %}/>
                                {%- else -%}
                                    <sonstige/>
                                {%- endif -%}
                            {%- else -%}
                                <sonstige/>
                            {%- endif -%}
                        {%- else -%}
                            <sonstige/>
                        {%- endif -%}
                        {%- if doc.custom_type_of_property -%}
                        <objektart_zusatz>{{ doc.custom_type_of_property }}</objektart_zusatz>
                        {%- endif -%}
                    </objektart>
                </objektkategorie>

                <geo>
                    {%- if doc.custom_pincode %}<plz>{{ doc.custom_pincode }}</plz>{% endif -%}
                    {%- if doc.custom_property_city %}<ort>{{ doc.custom_property_city }}</ort>{% endif -%}
                    {%- if doc.custom_latitude or doc.custom_longitude -%}
                    <geokoordinaten breitengrad="{{ doc.custom_latitude }}" laengengrad="{{ doc.custom_longitude }}"/>
                    {%- endif -%}
                    {%- if doc.custom_property_address %}<strasse>{{ doc.custom_property_address }}</strasse>{% endif -%}
                    <land iso_land="DEU"/>
                    {%- if doc.custom_district %}<regionaler_zusatz>{{ doc.custom_district }}</regionaler_zusatz>{% endif -%}
                    {%- if doc.custom_level_in_the_building is not none and doc.custom_level_in_the_building != "" -%}
                    <etage>{{ doc.custom_level_in_the_building }}</etage>
                    {%- endif -%}
                    <karten_makro>true</karten_makro>
                    {%- if doc.custom_flurstück %}<flurstueck>{{ doc.custom_flurstück }}</flurstueck>{% endif -%}
                </geo>

                <kontaktperson>
                    <email_zentrale>vermietung@axessio.de</email_zentrale>
                    {%- if doc.custom_contact_email %}<email_direkt>{{ doc.custom_contact_email }}</email_direkt>{% endif -%}
                    <tel_zentrale>0000000000</tel_zentrale>
                    <tel_handy>0000000000</tel_handy>
                    {%- if doc.custom_contact_phone %}<tel_direkt>{{ doc.custom_contact_phone }}</tel_direkt>{% endif -%}
                    {%- if doc.custom_property_manager %}<name>{{ doc.custom_property_manager }}</name>{% endif -%}
                </kontaktperson>

                {%- if doc.custom_building_superintendent -%}
                <weitere_adresse adressart="Hausmeister">
                    <name>{{ doc.custom_building_superintendent }}</name>
                </weitere_adresse>
                {%- endif -%}

                <preise>
                    {%- if doc.custom_new_rent is not none %}<kaltmiete>{{ doc.custom_new_rent }}</kaltmiete>{% endif -%}
                    {%- if doc.custom_new_operating_costs is not none %}<nebenkosten>{{ doc.custom_new_operating_costs }}</nebenkosten>{% endif -%}
                    {%- if doc.custom_additional_costs is not none %}<heizkosten>{{ doc.custom_additional_costs }}</heizkosten>{% endif -%}
                    {%- if doc.custom_plus_19_vat is not none -%}
                    <zzg_mehrwertsteuer>{{ 'true' if doc.custom_plus_19_vat in [True, 'true', 1, '1'] else 'false' }}</zzg_mehrwertsteuer>
                    {%- endif -%}
                    {%- if doc.custom_commissionfree is not none -%}
                    <provisionspflichtig>{{ 'false' if doc.custom_commissionfree in [True, 'true', 1, '1'] else 'true' }}</provisionspflichtig>
                    {%- endif -%}
                    {%- if doc.custom_commission_description %}<courtage_hinweis>{{ doc.custom_commission_description }}</courtage_hinweis>{% endif -%}
                    <waehrung iso_waehrung="EUR"/>
                    {%- if doc.security_deposit is not none %}<kaution>{{ doc.security_deposit }}</kaution>{% endif -%}
                    {%- if doc.security_deposit is not none %}<kaution_text>{{ doc.security_deposit }}</kaution_text>{% endif -%}

                    <!-- OPTIONAL EXTRA PRICE TAGS (Uncomment to use)
                    {%- if doc.custom_flat_rate_rent is not none %}<pauschalmiete>{{ doc.custom_flat_rate_rent }}</pauschalmiete>{% endif -%}
                    {%- if doc.custom_net_operating_costs is not none %}<betriebskostennetto>{{ doc.custom_net_operating_costs }}</betriebskostennetto>{% endif -%}
                    {%- if doc.custom_gross_rent is not none %}<gesamtmietebrutto>{{ doc.custom_gross_rent }}</gesamtmietebrutto>{% endif -%}
                    {%- if doc.custom_development_costs is not none %}<erschliessungskosten>{{ doc.custom_development_costs }}</erschliessungskosten>{% endif -%}
                    {%- if doc.custom_carport_rent is not none %}<stp_carport stellplatzmiete="{{ doc.custom_carport_rent }}"/></preise>{% endif -%}
                    {%- if doc.custom_parking_rent is not none %}<stp_freiplatz stellplatzmiete="{{ doc.custom_parking_rent }}"/></preise>{% endif -%}
                    -->
                </preise>

                <flaechen>
                    {%- if doc.builtup_area is not none %}<wohnflaeche>{{ doc.builtup_area }}</wohnflaeche>{% endif -%}
                    {%- if doc.carpet_area is not none %}<nutzflaeche>{{ doc.carpet_area }}</nutzflaeche>{% endif -%}
                    {%- if doc.custom_property_area is not none %}<gesamtflaeche>{{ doc.custom_property_area }}</gesamtflaeche>{% endif -%}
                    {%- if doc.common_bathroom is not none %}<anzahl_badezimmer>{{ doc.common_bathroom }}</anzahl_badezimmer>{% endif -%}
                    {%- if doc.master_bedroom is not none %}<anzahl_schlafzimmer>{{ doc.master_bedroom }}</anzahl_schlafzimmer>{% endif -%}
                    {%- if doc.custom_balcony is not none %}<anzahl_balkone>{{ doc.custom_balcony }}</anzahl_balkone>{% endif -%}
                    {%- if doc.bedroom is not none %}<anzahl_zimmer>{{ doc.bedroom }}</anzahl_zimmer>{% endif -%}
                </flaechen>

                <ausstattung>
                    {%- if doc.custom_type_of_heating -%}
                    <heizungsart OFEN="{{ 'true' if doc.custom_type_of_heating == 'Einzelofen' else 'false' }}"
                                 ZENTRAL="{{ 'true' if doc.custom_type_of_heating == 'Sammelheizung' else 'false' }}"/>
                    {%- endif -%}
                    
                    {%- if doc.custom_energy_carrier -%}
                    <befeuerung GAS="{{ 'true' if doc.custom_energy_carrier == 'Gas' else 'false' }}"
                               Solar="{{ 'true' if doc.custom_energy_carrier == 'Solar' else 'false' }}"
                               OEL="{{ 'true' if doc.custom_energy_carrier == 'Öl' else 'false' }}"
                               ELEKTRO="{{ 'true' if doc.custom_energy_carrier == 'Strom' else 'false' }}"
                               KOHLE="{{ 'true' if doc.custom_energy_carrier == 'Kohle' else 'false' }}"
                               FERN="{{ 'true' if doc.custom_energy_carrier == 'Fernwärme' else 'false' }}"/>
                    {%- endif -%}

                    {%- if doc.custom_elevator is not none -%}
                    <fahrstuhl>{{ 'true' if doc.custom_elevator in [True, 'true', 1, '1'] else 'false' }}</fahrstuhl>
                    {%- endif -%}
                    
                    {%- if doc.custom_garage_spaces is not none -%}
                    <stellplatzart GARAGE="{{ 'true' if doc.custom_garage_spaces else 'false' }}"/>
                    {%- endif -%}

                    {%- if doc.facing -%}
                    <ausricht_balkon_terrasse NORD="{{ 'true' if doc.facing == 'North' else 'false' }}"
                                              NORDOST="{{ 'true' if doc.facing == 'North-East' else 'false' }}"
                                              OST="{{ 'true' if doc.facing == 'East' else 'false' }}"
                                              SUEDOST="{{ 'true' if doc.facing == 'South-East' else 'false' }}"
                                              SUED="{{ 'true' if doc.facing == 'South' else 'false' }}"
                                              SUEDWEST="{{ 'true' if doc.facing == 'South-West' else 'false' }}"
                                              WEST="{{ 'true' if doc.facing == 'West' else 'false' }}"
                                              NORDWEST="{{ 'true' if doc.facing == 'North-West' else 'false' }}"/>
                    {%- endif -%}

                    {%- if doc.furnished -%}
                    <moebliert moeb="{{ 'VOLL' if doc.furnished in [True, 'true', 1, '1'] else 'NICHT_MOEBLIERT' }}"/>
                    {%- endif -%}

                    <!-- OPTIONAL EXTRA FITTING TAGS (Uncomment to use)
                    <boden FLIESEN="{{ 'true' if doc.custom_tiles else 'false' }}" TEPPICH="{{ 'true' if doc.custom_carpet else 'false' }}" PARKETT="{{ 'true' if doc.custom_parquet else 'false' }}"/>
                    <bad DUSCHE="{{ 'true' if doc.custom_shower else 'false' }}" WANNE="{{ 'true' if doc.custom_tub else 'false' }}" FENSTER="{{ 'true' if doc.custom_window else 'false' }}"/>
                    <kueche EBK="{{ 'true' if doc.custom_fitted_kitchen else 'false' }}" OFFEN="{{ 'true' if doc.custom_open_kitchen else 'false' }}"/>
                    <kamin>{{ 'true' if doc.custom_fireplace else 'false' }}</kamin>
                    <klimatisiert>{{ 'true' if doc.custom_air_conditioned else 'false' }}</klimatisiert>
                    <sauna>{{ 'true' if doc.custom_sauna else 'false' }}</sauna>
                    <swimmingpool>{{ 'true' if doc.custom_pool else 'false' }}</swimmingpool>
                    <wintergarten>{{ 'true' if doc.custom_conservatory else 'false' }}</wintergarten>
                    <rollstuhlgerecht>{{ 'true' if doc.custom_wheelchair_accessible else 'false' }}</rollstuhlgerecht>
                    <barrierefrei>{{ 'true' if doc.custom_barrier_free else 'false' }}</barrierefrei>
                    {%- if doc.custom_has_cellar %}<unterkellert keller="{{ doc.custom_has_cellar }}"/><% endif -%}
                    <abstellraum>{{ 'true' if doc.custom_utility_room else 'false' }}</abstellraum>
                    <gaestewc>{{ 'true' if doc.custom_guest_toilet else 'false' }}</gaestewc>
                    <seniorengerecht>{{ 'true' if doc.custom_senior_friendly else 'false' }}</seniorengerecht>
                    -->
                </ausstattung>

                <zustand_angaben>
                    {%- if doc.custom_year_of_construction -%}
                    <baujahr>{{ doc.custom_year_of_construction }}</baujahr>
                    {%- endif -%}
                    {%- if doc.custom_last_renovation -%}
                    <letztemodernisierung>{{ doc.custom_last_renovation }}</letztemodernisierung>
                    {%- endif -%}
                    {%- if doc.custom_condition -%}
                    <zustand zustand_art="{{ doc.custom_condition }}"/>
                    {%- endif -%}
                    {%- if doc.custom_hot_water_preparation -%}
                    <energiepass>
                        <mitwarmwasser>{{ 'true' if doc.custom_hot_water_preparation in ['Gastherme', 'Zentralheizung', 'E-Boiler', 'Elektrodurchlauferhitzer'] else 'false' }}</mitwarmwasser>
                    </energiepass>
                    {%- endif -%}

                    <!-- OPTIONAL EXTRA CONDITION TAGS (Uncomment to use)
                    {%- if doc.custom_building_age_category %}<alter alter_attr="{{ doc.custom_building_age_category }}"/><% endif -%}
                    {%- if doc.custom_infrastructure_status %}<erschliessung erschl_attr="{{ doc.custom_infrastructure_status }}"/><% endif -%}
                    {%- if doc.custom_building_regulations %}<bebaubar_nach bebaubar_attr="{{ doc.custom_building_regulations }}"/><% endif -%}
                    -->

                    {# --- Energy Certificate: pulls values dynamically from linked DocType and applies formatting --- #}
                    {%- if doc.custom_energy_certificate -%}
                        {%- set cert = frappe.get_doc("Energy Certificate Link", doc.custom_energy_certificate) -%}
                        {%- if cert -%}
                        <energiepass>
                            <epart>{{ cert.energiepass_art or 'VERBRAUCH' }}</epart>
                            {%- if cert.gültig_bis %}<gueltig_bis>{{ cert.gültig_bis | format_immowelt_date }}</gueltig_bis>{% endif -%}
                            {%- if cert.energiepass_kennwert %}<energieverbrauchkennwert>{{ cert.energiepass_kennwert | format_decimal }}</energieverbrauchkennwert>{% endif -%}
                            <mitwarmwasser>{{ 'true' if cert.mitwarmwasser in [True, 'true', 1, '1'] else 'false' }}</mitwarmwasser>
                            {%- if cert.energieeffizienzklasse %}<wertklasse>{{ cert.energieeffizienzklasse }}</wertklasse>{% endif -%}
                            {%- if cert.ausstelldatum %}<ausstelldatum>{{ cert.ausstelldatum }}</ausstelldatum>{% endif -%}
                        </energiepass>
                        {%- endif -%}
                    {%- endif -%}
                </zustand_angaben>

                <bewertung>
                    <feld>
                        <name>Anschaffungsdatum</name>
                        <wert>{{ doc.custom_date_of_purchase }}</wert>
                    </feld>
                    <feld>
                        <name>Bodenwert</name>
                        <wert>{{ doc.custom_land_value_per_sqm }}</wert>
                    </feld>
                </bewertung>

                <!-- OPTIONAL INFRASTRUCTURE TAGS (Uncomment to use)
                <infrastruktur>
                    <zulieferung>{{ 'true' if doc.custom_delivery_possible else 'false' }}</zulieferung>
                    {%- if doc.custom_view_type %}<ausblick blick="{{ doc.custom_view_type }}"/><% endif -%}
                    {%- if doc.custom_distance_to_school %}<distanzen distanz_zu="HAUPTSCHULE">{{ doc.custom_distance_to_school }}</distanzen>{% endif -%}
                    {%- if doc.custom_distance_to_lake %}<distanzen_sport distanz_zu_sport="SEE">{{ doc.custom_distance_to_lake }}</distanzen_sport>{% endif -%}
                </infrastruktur>
                -->

                <freitexte>
                    {%- if doc.custom_marketing_title -%}
                    <objekttitel>{{ doc.custom_marketing_title }}</objekttitel>
                    {%- endif -%}
                    {%- if doc.custom_location_short -%}
                    <dreizeiler>{{ doc.custom_location_short }}</dreizeiler>
                    {%- endif -%}
                    {%- if doc.custom_marketing_description -%}
                    <objektbeschreibung>{{ doc.custom_marketing_description }}</objektbeschreibung>
                    {%- endif -%}
                    {%- if doc.custom_additional_information -%}
                    <sonstige_angaben>{{ doc.custom_additional_information }}</sonstige_angaben>
                    {%- endif -%}
                    <objekt_text lang="GER"/>
                </freitexte>

                {# --- Attachment Gallery: dynamically groups hero images as TITELBILD and others as BILD --- #}
                {%- if doc.custom_image_gallery -%}
                <anhaenge>
                    {# --- Check if any image is explicitly flagged as hero_image --- #}
                    {%- set ns_hero = namespace(has_hero=false) -%}
                    {%- for row in doc.custom_image_gallery -%}
                        {%- if row.is_hero_image -%}
                            {%- set ns_hero.has_hero = true -%}
                        {%- endif -%}
                    {%- endfor -%}

                    {%- for row in doc.custom_image_gallery -%}
                        {%- set img_path = row.get("picture") -%}
                        {%- if img_path -%}
                            {# --- If hero is found, use is_hero_image. Otherwise fallback to first image as hero --- #}
                            {%- set is_hero = false -%}
                            {%- if ns_hero.has_hero -%}
                                {%- if row.is_hero_image -%}
                                    {%- set is_hero = true -%}
                                {%- endif -%}
                            {%- else -%}
                                {%- if loop.first -%}
                                    {%- set is_hero = true -%}
                                {%- endif -%}
                            {%- endif -%}
                            
                            <anhang location="EXTERN" gruppe="{{ 'TITELBILD' if is_hero else 'BILD' }}">
                                <format>{{ img_path.split('.')[-1].upper() if '.' in img_path else 'JPEG' }}</format>
                                <daten>
                                    <pfad>{{ img_path if img_path.startswith(('http://', 'https://')) else ((source.base_media_url or frappe.utils.get_url()).rstrip('/') ~ '/' ~ img_path.lstrip('/')) }}</pfad>
                                </daten>
                            </anhang>
                        {%- endif -%}
                    {%- endfor -%}
                </anhaenge>
                {%- endif -%}

                <verwaltung_objekt>
                    {%- if doc.custom_marketing_status -%}
                    <reserviert>{{ doc.custom_marketing_status }}</reserviert>
                    {%- endif -%}
                    {%- if doc.status -%}
                    <vermietet>{{ 'true' if doc.status == 'Rented' else 'false' }}</vermietet>
                    {%- endif -%}
                    {%- if doc.custom_available_from -%}
                    <verfuegbar_ab>{{ doc.custom_available_from }}</verfuegbar_ab>
                    {%- endif -%}
                    {%- if doc.custom_pets_allowed is not none -%}
                    <haustiere>{{ 'true' if doc.custom_pets_allowed in [True, 'true', 1, '1'] else 'false' }}</haustiere>
                    {%- endif -%}
                    {%- if doc.custom_monument_protection is not none -%}
                    <denkmalgeschuetzt>{{ 'true' if doc.custom_monument_protection in [True, 'true', 1, '1'] else 'false' }}</denkmalgeschuetzt>
                    {%- endif -%}
                </verwaltung_objekt>

                <verwaltung_techn>
                    <objektnr_intern>{{ doc.name }}</objektnr_intern>
                    <objektnr_extern>{{ doc.name }}</objektnr_extern>
                    <aktion aktionart="{{ source.transfer_mode }}"/>
                    <openimmo_obid>{{ doc.name }}</openimmo_obid>
                    <stand_vom>{{ doc.modified }}</stand_vom>
                    {%- if doc.custom_available_from -%}
                    <aktiv_von>{{ doc.custom_available_from }}</aktiv_von>
                    {%- endif -%}
                </verwaltung_techn>
            </immobilie>
        {%- endfor -%}
    </anbieter>
</openimmo>
"""
