<?xml version="1.0"?>

<!-- This is an xsl stylesheet to add styles to an OGR generated KML file -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
				xmlns:kml="http://www.opengis.net/kml/2.2" version="1.0">
	<xsl:output method="xml" indent="yes" omit-xml-declaration="no" encoding="utf-8"/>

	<!-- In general, just pass through all elements and attributes -->
	<xsl:template match="*">		
		<xsl:copy>
			<xsl:copy-of select="@*" />
			<xsl:apply-templates />
		</xsl:copy>
	</xsl:template>

	<!-- We want to eliminate any embedded style because we don't want to hide the external styles -->
	<xsl:template match="kml:Style" />
	
  <!-- Eliminate Schema and ExtendedData -->
	<xsl:template match="kml:Schema" />
	<xsl:template match="kml:ExtendedData" />

	<xsl:template match="kml:Document">
		<xsl:copy>
			<xsl:copy-of select="@*" />
			<Style id="Cat0">
				<PolyStyle>
					<color>00000000</color>
					<fill>0</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat1">
				<PolyStyle>
					<color>99009600</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat2">
				<PolyStyle>
					<color>9900c800</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat3">
				<PolyStyle>
					<color>9900ff00</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat4">
				<PolyStyle>
					<color>9900fcfc</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat5">
				<PolyStyle>
					<color>9996ffff</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat6">
				<PolyStyle>
					<color>99007eff</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat7">
				<PolyStyle>
					<color>990000ff</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat8">
				<PolyStyle>
					<color>994c0099</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<Style id="Cat9">
				<PolyStyle>
					<color>9926004c</color>
					<fill>1</fill>
					<outline>0</outline>
				</PolyStyle>
			</Style>
			<xsl:apply-templates />
		</xsl:copy>
	</xsl:template>

	<xsl:template match="kml:Placemark">				
		<xsl:copy>
			<xsl:copy-of select="@*" />
			<styleUrl><xsl:value-of select="./kml:ExtendedData/kml:SchemaData/kml:SimpleData[@name='Category']" /></styleUrl>
			<xsl:apply-templates />
		</xsl:copy>
	</xsl:template>
	
</xsl:stylesheet>
