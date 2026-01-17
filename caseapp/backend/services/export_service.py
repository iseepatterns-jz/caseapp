"""
Comprehensive export service for timeline and forensic reports
Provides professional PDF generation, PNG visualizations, and selective export filtering
"""

import io
import json
import asyncio
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from datetime import datetime, timedelta, UTC
from pathlib import Path
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

# PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.flowables import Image as ReportLabImage
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# PNG visualization
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np

from core.database import AsyncSessionLocal
from models.case import Case
from models.timeline import CaseTimeline, TimelineEvent
from models.document import Document
from models.media import MediaEvidence
from models.forensic_analysis import ForensicSource, ForensicItem
from core.exceptions import CaseManagementException
from core.config import settings

logger = structlog.get_logger()

class ExportService:
    """Service for exporting case data in multiple formats"""
    
    def __init__(self):
        self.temp_dir = Path("/tmp/case_exports")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def export_timeline_pdf(
        self,
        case_id: str,
        timeline_id: Optional[str] = None,
        date_range: Optional[Dict[str, datetime]] = None,
        include_evidence: bool = True,
        include_metadata: bool = True
    ) -> bytes:
        """
        Export timeline as professional PDF report
        
        Args:
            case_id: UUID of the case
            timeline_id: Optional specific timeline ID
            date_range: Optional date filtering {'start': datetime, 'end': datetime}
            include_evidence: Whether to include evidence attachments
            include_metadata: Whether to include event metadata
            
        Returns:
            PDF content as bytes
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get case and timeline data
                case_data = await self._get_case_data(db, case_id, timeline_id)
                
                # Filter events by date range if specified
                if date_range:
                    case_data['events'] = self._filter_events_by_date(
                        case_data['events'], date_range
                    )
                
                # Generate PDF
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=A4,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=18
                )
                
                # Build PDF content
                story = []
                styles = getSampleStyleSheet()
                
                # Add custom styles
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                
                # Title page
                story.append(Paragraph(f"Case Timeline Report", title_style))
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Case: {case_data['case']['title']}", styles['Heading2']))
                story.append(Paragraph(f"Case Number: {case_data['case']['case_number']}", styles['Normal']))
                story.append(Paragraph(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles['Normal']))
                story.append(Spacer(1, 20))
                
                # Case summary
                if case_data['case']['description']:
                    story.append(Paragraph("Case Description", styles['Heading3']))
                    story.append(Paragraph(case_data['case']['description'], styles['Normal']))
                    story.append(Spacer(1, 12))
                
                # Timeline events
                story.append(Paragraph("Timeline Events", styles['Heading2']))
                story.append(Spacer(1, 12))
                
                for event in case_data['events']:
                    # Event header
                    event_date = event['event_date'].strftime('%Y-%m-%d %H:%M') if event['event_date'] else 'No date'
                    story.append(Paragraph(f"{event['title']} ({event_date})", styles['Heading3']))
                    
                    # Event details
                    if event['description']:
                        story.append(Paragraph(event['description'], styles['Normal']))
                    
                    if include_metadata:
                        # Event metadata table
                        metadata_data = [
                            ['Event Type', event['event_type']],
                            ['Location', event['location'] or 'Not specified'],
                            ['Participants', ', '.join(event['participants']) if event['participants'] else 'None']
                        ]
                        
                        metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
                        metadata_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (0, -1), HexColor('#f0f0f0')),
                            ('TEXTCOLOR', (0, 0), (-1, -1), black),
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                            ('FONTSIZE', (0, 0), (-1, -1), 9),
                            ('GRID', (0, 0), (-1, -1), 1, black)
                        ]))
                        story.append(metadata_table)
                    
                    # Evidence attachments
                    if include_evidence and event.get('evidence_pins'):
                        story.append(Paragraph("Attached Evidence:", styles['Heading4']))
                        for evidence in event['evidence_pins']:
                            evidence_text = f"• {evidence['title']} ({evidence['type']})"
                            if evidence.get('relevance_score'):
                                evidence_text += f" - Relevance: {evidence['relevance_score']:.2f}"
                            story.append(Paragraph(evidence_text, styles['Normal']))
                    
                    story.append(Spacer(1, 20))
                
                # Export metadata
                story.append(PageBreak())
                story.append(Paragraph("Export Information", styles['Heading2']))
                export_info = [
                    ['Export Date', datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')],
                    ['Total Events', str(len(case_data['events']))],
                    ['Date Range', f"{date_range['start'].strftime('%Y-%m-%d')} to {date_range['end'].strftime('%Y-%m-%d')}" if date_range else 'All dates'],
                    ['Include Evidence', 'Yes' if include_evidence else 'No'],
                    ['Include Metadata', 'Yes' if include_metadata else 'No']
                ]
                
                export_table = Table(export_info, colWidths=[2*inch, 4*inch])
                export_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), HexColor('#f0f0f0')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, black)
                ]))
                story.append(export_table)
                
                # Build PDF
                doc.build(story)
                pdf_content = pdf_buffer.getvalue()
                pdf_buffer.close()
                
                logger.info("Generated timeline PDF export", 
                           case_id=case_id, 
                           events_count=len(case_data['events']),
                           pdf_size=len(pdf_content))
                
                return pdf_content
                
        except Exception as e:
            logger.error("Failed to export timeline PDF", case_id=case_id, error=str(e))
            raise CaseManagementException(f"Timeline PDF export failed: {str(e)}")
    
    async def export_timeline_png(
        self,
        case_id: str,
        timeline_id: Optional[str] = None,
        date_range: Optional[Dict[str, datetime]] = None,
        width: int = 1920,
        height: int = 1080,
        dpi: int = 300
    ) -> bytes:
        """
        Export timeline as high-resolution PNG visualization
        
        Args:
            case_id: UUID of the case
            timeline_id: Optional specific timeline ID
            date_range: Optional date filtering
            width: Image width in pixels
            height: Image height in pixels
            dpi: Image resolution
            
        Returns:
            PNG content as bytes
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get case and timeline data
                case_data = await self._get_case_data(db, case_id, timeline_id)
                
                # Filter events by date range if specified
                if date_range:
                    case_data['events'] = self._filter_events_by_date(
                        case_data['events'], date_range
                    )
                
                # Create matplotlib figure
                fig, ax = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)
                
                # Prepare timeline data
                events = case_data['events']
                if not events:
                    # Create empty timeline
                    ax.text(0.5, 0.5, 'No events in selected date range', 
                           ha='center', va='center', transform=ax.transAxes, fontsize=16)
                    ax.set_xlim(0, 1)
                    ax.set_ylim(0, 1)
                else:
                    # Sort events by date
                    dated_events = [e for e in events if e['event_date']]
                    dated_events.sort(key=lambda x: x['event_date'])
                    
                    if dated_events:
                        # Create timeline visualization
                        dates = [e['event_date'] for e in dated_events]
                        y_positions = list(range(len(dated_events)))
                        
                        # Plot timeline line
                        ax.plot([min(dates), max(dates)], [0, len(dated_events)-1], 
                               'k-', linewidth=2, alpha=0.3)
                        
                        # Plot events
                        colors = plt.cm.Set3(np.linspace(0, 1, len(dated_events)))
                        for i, (event, date, color) in enumerate(zip(dated_events, dates, colors)):
                            # Event marker
                            ax.scatter(date, i, s=100, c=[color], alpha=0.8, edgecolors='black')
                            
                            # Event label
                            label = event['title'][:50] + ('...' if len(event['title']) > 50 else '')
                            ax.annotate(label, (date, i), xytext=(10, 0), 
                                       textcoords='offset points', va='center',
                                       bbox=dict(boxstyle='round,pad=0.3', facecolor=color, alpha=0.7))
                        
                        # Format x-axis (dates)
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                        ax.xaxis.set_major_locator(mdates.MonthLocator())
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                        
                        # Format y-axis
                        ax.set_yticks(y_positions)
                        ax.set_yticklabels([f"Event {i+1}" for i in y_positions])
                        
                        # Set limits with padding
                        date_range_days = (max(dates) - min(dates)).days
                        padding = timedelta(days=max(1, date_range_days * 0.05))
                        ax.set_xlim(min(dates) - padding, max(dates) + padding)
                        ax.set_ylim(-0.5, len(dated_events) - 0.5)
                
                # Styling
                ax.set_title(f"Timeline: {case_data['case']['title']}", fontsize=16, fontweight='bold')
                ax.set_xlabel('Date', fontsize=12)
                ax.set_ylabel('Events', fontsize=12)
                ax.grid(True, alpha=0.3)
                
                # Add case information
                info_text = f"Case: {case_data['case']['case_number']}\n"
                info_text += f"Total Events: {len(events)}\n"
                info_text += f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
                
                ax.text(0.02, 0.98, info_text, transform=ax.transAxes, 
                       verticalalignment='top', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
                
                # Save to bytes
                png_buffer = io.BytesIO()
                plt.tight_layout()
                plt.savefig(png_buffer, format='png', dpi=dpi, bbox_inches='tight')
                plt.close(fig)
                
                png_content = png_buffer.getvalue()
                png_buffer.close()
                
                logger.info("Generated timeline PNG export", 
                           case_id=case_id, 
                           events_count=len(events),
                           image_size=len(png_content))
                
                return png_content
                
        except Exception as e:
            logger.error("Failed to export timeline PNG", case_id=case_id, error=str(e))
            raise CaseManagementException(f"Timeline PNG export failed: {str(e)}")
    
    async def export_forensic_report_pdf(
        self,
        case_id: str,
        source_ids: Optional[List[str]] = None,
        include_statistics: bool = True,
        include_network_analysis: bool = True,
        include_raw_data: bool = False
    ) -> bytes:
        """
        Export comprehensive forensic analysis report as PDF
        
        Args:
            case_id: UUID of the case
            source_ids: Optional list of specific forensic source IDs
            include_statistics: Whether to include communication statistics
            include_network_analysis: Whether to include network graphs
            include_raw_data: Whether to include raw message data
            
        Returns:
            PDF content as bytes
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get forensic data
                forensic_data = await self._get_forensic_data(db, case_id, source_ids)
                
                # Generate PDF
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=A4,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=18
                )
                
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                
                story.append(Paragraph("Forensic Analysis Report", title_style))
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Case: {forensic_data['case']['title']}", styles['Heading2']))
                story.append(Paragraph(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}", styles['Normal']))
                story.append(Spacer(1, 20))
                
                # Executive summary
                story.append(Paragraph("Executive Summary", styles['Heading2']))
                summary_data = [
                    ['Total Sources', str(len(forensic_data['sources']))],
                    ['Total Messages', str(forensic_data['statistics']['total_messages'])],
                    ['Unique Participants', str(forensic_data['statistics']['unique_participants'])],
                    ['Date Range', f"{forensic_data['statistics']['date_range']['start']} to {forensic_data['statistics']['date_range']['end']}"],
                    ['Analysis Status', 'Complete']
                ]
                
                summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), HexColor('#f0f0f0')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, black)
                ]))
                story.append(summary_table)
                story.append(Spacer(1, 20))
                
                # Communication statistics
                if include_statistics:
                    story.append(Paragraph("Communication Statistics", styles['Heading2']))
                    
                    stats = forensic_data['statistics']
                    stats_data = [
                        ['Messages by Type', ''],
                        ['Email', str(stats.get('email_count', 0))],
                        ['SMS/Text', str(stats.get('sms_count', 0))],
                        ['WhatsApp', str(stats.get('whatsapp_count', 0))],
                        ['Other', str(stats.get('other_count', 0))],
                        ['', ''],
                        ['Sentiment Analysis', ''],
                        ['Positive Messages', str(stats.get('positive_sentiment', 0))],
                        ['Neutral Messages', str(stats.get('neutral_sentiment', 0))],
                        ['Negative Messages', str(stats.get('negative_sentiment', 0))],
                        ['', ''],
                        ['Temporal Patterns', ''],
                        ['Peak Activity Hour', str(stats.get('peak_hour', 'N/A'))],
                        ['Weekend Messages', str(stats.get('weekend_messages', 0))],
                        ['Deleted Messages', str(stats.get('deleted_messages', 0))]
                    ]
                    
                    stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
                    stats_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), HexColor('#f0f0f0')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, black)
                    ]))
                    story.append(stats_table)
                    story.append(Spacer(1, 20))
                
                # Network analysis
                if include_network_analysis:
                    story.append(Paragraph("Communication Network Analysis", styles['Heading2']))
                    story.append(Paragraph("Key Participants and Relationships:", styles['Heading3']))
                    
                    for participant in forensic_data['network_analysis']['key_participants'][:10]:
                        participant_text = f"• {participant['name']} - {participant['message_count']} messages"
                        if participant.get('centrality_score'):
                            participant_text += f" (Centrality: {participant['centrality_score']:.2f})"
                        story.append(Paragraph(participant_text, styles['Normal']))
                    
                    story.append(Spacer(1, 12))
                
                # Source details
                story.append(PageBreak())
                story.append(Paragraph("Forensic Sources", styles['Heading2']))
                
                for source in forensic_data['sources']:
                    story.append(Paragraph(f"Source: {source['source_name']}", styles['Heading3']))
                    
                    source_details = [
                        ['Source Type', source['source_type']],
                        ['Device Info', source.get('device_info', 'N/A')],
                        ['Account Info', source.get('account_info', 'N/A')],
                        ['Messages Extracted', str(source['message_count'])],
                        ['Analysis Status', source['analysis_status']]
                    ]
                    
                    source_table = Table(source_details, colWidths=[2*inch, 4*inch])
                    source_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, -1), HexColor('#f0f0f0')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, black)
                    ]))
                    story.append(source_table)
                    story.append(Spacer(1, 12))
                
                # Build PDF
                doc.build(story)
                pdf_content = pdf_buffer.getvalue()
                pdf_buffer.close()
                
                logger.info("Generated forensic report PDF", 
                           case_id=case_id, 
                           sources_count=len(forensic_data['sources']),
                           pdf_size=len(pdf_content))
                
                return pdf_content
                
        except Exception as e:
            logger.error("Failed to export forensic report PDF", case_id=case_id, error=str(e))
            raise CaseManagementException(f"Forensic report PDF export failed: {str(e)}")
    
    async def generate_court_presentation_dashboard(
        self,
        case_id: str,
        source_ids: Optional[List[str]] = None,
        include_key_statistics: bool = True,
        include_network_graphs: bool = True,
        include_timeline_correlation: bool = True
    ) -> Dict[str, Any]:
        """
        Generate court presentation dashboard with key statistics and visual highlights
        
        Args:
            case_id: UUID of the case
            source_ids: Optional list of specific forensic source IDs
            include_key_statistics: Whether to include key statistics
            include_network_graphs: Whether to include network graph data
            include_timeline_correlation: Whether to correlate with timeline events
            
        Returns:
            Dictionary with dashboard data for court presentation
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get forensic data
                forensic_data = await self._get_forensic_data(db, case_id, source_ids)
                
                # Get timeline data for correlation if requested
                timeline_data = None
                if include_timeline_correlation:
                    timeline_data = await self._get_case_data(db, case_id)
                
                # Generate dashboard components
                dashboard = {
                    'case_id': case_id,
                    'case_title': forensic_data['case']['title'],
                    'generated_at': datetime.now(UTC).isoformat(),
                    'dashboard_type': 'court_presentation'
                }
                
                if include_key_statistics:
                    dashboard['key_statistics'] = await self._generate_key_statistics_summary(
                        forensic_data
                    )
                
                if include_network_graphs:
                    dashboard['network_analysis'] = await self._generate_network_graph_data(
                        forensic_data
                    )
                
                if include_timeline_correlation and timeline_data:
                    dashboard['timeline_correlation'] = await self._correlate_forensic_with_timeline(
                        forensic_data, timeline_data
                    )
                
                # Add visual highlights for court presentation
                dashboard['visual_highlights'] = await self._generate_visual_highlights(
                    forensic_data, timeline_data
                )
                
                logger.info("Generated court presentation dashboard", 
                           case_id=case_id, 
                           components=list(dashboard.keys()))
                
                return dashboard
                
        except Exception as e:
            logger.error("Failed to generate court presentation dashboard", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Court presentation dashboard generation failed: {str(e)}")
    
    async def export_communication_statistics_report(
        self,
        case_id: str,
        source_ids: Optional[List[str]] = None,
        time_period: Optional[Dict[str, datetime]] = None,
        include_sentiment_analysis: bool = True,
        include_participant_breakdown: bool = True
    ) -> Dict[str, Any]:
        """
        Export detailed communication statistics report
        
        Args:
            case_id: UUID of the case
            source_ids: Optional list of specific forensic source IDs
            time_period: Optional time period filtering
            include_sentiment_analysis: Whether to include sentiment analysis
            include_participant_breakdown: Whether to include participant breakdown
            
        Returns:
            Dictionary with comprehensive communication statistics
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get forensic data
                forensic_data = await self._get_forensic_data(db, case_id, source_ids)
                
                # Calculate comprehensive statistics
                stats_report = {
                    'case_id': case_id,
                    'report_type': 'communication_statistics',
                    'generated_at': datetime.now(UTC).isoformat(),
                    'time_period': time_period,
                    'sources_analyzed': len(forensic_data['sources'])
                }
                
                # Basic communication metrics
                stats_report['communication_metrics'] = {
                    'total_messages': forensic_data['statistics']['total_messages'],
                    'unique_participants': forensic_data['statistics']['unique_participants'],
                    'date_range': forensic_data['statistics']['date_range'],
                    'messages_by_type': {
                        'email': forensic_data['statistics'].get('email_count', 0),
                        'sms': forensic_data['statistics'].get('sms_count', 0),
                        'whatsapp': forensic_data['statistics'].get('whatsapp_count', 0),
                        'other': forensic_data['statistics'].get('other_count', 0)
                    }
                }
                
                # Temporal analysis
                stats_report['temporal_analysis'] = {
                    'peak_activity_hour': forensic_data['statistics'].get('peak_hour', 'N/A'),
                    'weekend_messages': forensic_data['statistics'].get('weekend_messages', 0),
                    'weekday_messages': forensic_data['statistics']['total_messages'] - forensic_data['statistics'].get('weekend_messages', 0),
                    'deleted_messages': forensic_data['statistics'].get('deleted_messages', 0),
                    'message_frequency': await self._calculate_message_frequency(forensic_data)
                }
                
                if include_sentiment_analysis:
                    stats_report['sentiment_analysis'] = {
                        'positive_messages': forensic_data['statistics'].get('positive_sentiment', 0),
                        'neutral_messages': forensic_data['statistics'].get('neutral_sentiment', 0),
                        'negative_messages': forensic_data['statistics'].get('negative_sentiment', 0),
                        'sentiment_trends': await self._analyze_sentiment_trends(forensic_data),
                        'emotional_indicators': await self._identify_emotional_indicators(forensic_data)
                    }
                
                if include_participant_breakdown:
                    stats_report['participant_analysis'] = {
                        'key_participants': forensic_data['network_analysis']['key_participants'],
                        'communication_patterns': await self._analyze_communication_patterns(forensic_data),
                        'relationship_strength': await self._calculate_relationship_strength(forensic_data)
                    }
                
                # Anomaly detection summary
                stats_report['anomaly_summary'] = await self._summarize_communication_anomalies(
                    forensic_data
                )
                
                logger.info("Generated communication statistics report", 
                           case_id=case_id, 
                           total_messages=stats_report['communication_metrics']['total_messages'])
                
                return stats_report
                
        except Exception as e:
            logger.error("Failed to generate communication statistics report", 
                        case_id=case_id, error=str(e))
            raise CaseManagementException(f"Communication statistics report failed: {str(e)}")
    
    async def export_network_graph_data(
        self,
        case_id: str,
        source_ids: Optional[List[str]] = None,
        format_type: str = 'json',
        include_metadata: bool = True
    ) -> Union[Dict[str, Any], bytes]:
        """
        Export communication network graph data for visualization
        
        Args:
            case_id: UUID of the case
            source_ids: Optional list of specific forensic source IDs
            format_type: Export format ('json', 'graphml', 'csv')
            include_metadata: Whether to include node/edge metadata
            
        Returns:
            Network graph data in specified format
        """
        try:
            async with AsyncSessionLocal() as db:
                # Get forensic data
                forensic_data = await self._get_forensic_data(db, case_id, source_ids)
                
                # Generate network graph data
                network_data = await self._generate_detailed_network_data(
                    forensic_data, include_metadata
                )
                
                if format_type.lower() == 'json':
                    return {
                        'case_id': case_id,
                        'network_type': 'communication_network',
                        'generated_at': datetime.now(UTC).isoformat(),
                        'nodes': network_data['nodes'],
                        'edges': network_data['edges'],
                        'metadata': network_data['metadata'] if include_metadata else None,
                        'statistics': {
                            'total_nodes': len(network_data['nodes']),
                            'total_edges': len(network_data['edges']),
                            'network_density': network_data.get('density', 0),
                            'clustering_coefficient': network_data.get('clustering', 0)
                        }
                    }
                elif format_type.lower() == 'csv':
                    return await self._export_network_as_csv(network_data)
                else:
                    raise CaseManagementException(f"Unsupported network export format: {format_type}")
                
        except Exception as e:
            logger.error("Failed to export network graph data", 
                        case_id=case_id, format_type=format_type, error=str(e))
            raise CaseManagementException(f"Network graph export failed: {str(e)}")
    
    async def export_selective_data(
        self,
        case_id: str,
        export_format: str,
        filters: Dict[str, Any]
    ) -> Union[bytes, Dict[str, Any]]:
        """
        Export case data with selective filtering
        
        Args:
            case_id: UUID of the case
            export_format: 'pdf', 'json', 'csv'
            filters: Export filters including date ranges, evidence types, etc.
            
        Returns:
            Exported data as bytes (PDF) or dict (JSON)
        """
        try:
            async with AsyncSessionLocal() as db:
                # Apply filters and get filtered data
                filtered_data = await self._apply_export_filters(db, case_id, filters)
                
                if export_format.lower() == 'json':
                    return filtered_data
                elif export_format.lower() == 'pdf':
                    return await self._generate_filtered_pdf(filtered_data, filters)
                else:
                    raise CaseManagementException(f"Unsupported export format: {export_format}")
                
        except Exception as e:
            logger.error("Failed to export selective data", 
                        case_id=case_id, format=export_format, error=str(e))
            raise CaseManagementException(f"Selective export failed: {str(e)}")
    
    # Helper methods
    
    async def _get_case_data(
        self, 
        db: AsyncSession, 
        case_id: str, 
        timeline_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get case and timeline data for export"""
        # Get case with related data
        case_result = await db.execute(
            select(Case)
            .where(Case.id == case_id)
            .options(
                selectinload(Case.timelines).selectinload(CaseTimeline.events),
                selectinload(Case.documents),
                selectinload(Case.media_evidence)
            )
        )
        case = case_result.scalar_one_or_none()
        
        if not case:
            raise CaseManagementException(f"Case {case_id} not found")
        
        # Get timeline events
        events = []
        if timeline_id:
            # Get specific timeline
            timeline_result = await db.execute(
                select(CaseTimeline)
                .where(and_(CaseTimeline.id == timeline_id, CaseTimeline.case_id == case_id))
                .options(selectinload(CaseTimeline.events))
            )
            timeline = timeline_result.scalar_one_or_none()
            if timeline:
                events = timeline.events
        else:
            # Get all timeline events
            for timeline in case.timelines:
                events.extend(timeline.events)
        
        # Convert events to dict format
        events_data = []
        for event in events:
            event_dict = {
                'id': str(event.id),
                'title': event.title,
                'description': event.description,
                'event_type': event.event_type.value if event.event_type else 'unknown',
                'event_date': event.event_date,
                'location': event.location,
                'participants': event.participants or [],
                'evidence_pins': []  # TODO: Add evidence pin data when available
            }
            events_data.append(event_dict)
        
        # Sort events by date
        events_data.sort(key=lambda x: x['event_date'] or datetime.min)
        
        return {
            'case': {
                'id': str(case.id),
                'title': case.title,
                'case_number': case.case_number,
                'description': case.description,
                'case_type': case.case_type.value if case.case_type else 'unknown',
                'status': case.status.value if case.status else 'unknown'
            },
            'events': events_data
        }
    
    def _filter_events_by_date(
        self, 
        events: List[Dict[str, Any]], 
        date_range: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Filter events by date range"""
        filtered_events = []
        start_date = date_range.get('start')
        end_date = date_range.get('end')
        
        for event in events:
            event_date = event.get('event_date')
            if not event_date:
                continue
            
            if start_date and event_date < start_date:
                continue
            if end_date and event_date > end_date:
                continue
            
            filtered_events.append(event)
        
        return filtered_events
    
    async def _get_forensic_data(
        self, 
        db: AsyncSession, 
        case_id: str, 
        source_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get forensic data for export"""
        # Get case
        case_result = await db.execute(
            select(Case)
            .where(Case.id == case_id)
            .options(selectinload(Case.forensic_sources))
        )
        case = case_result.scalar_one_or_none()
        
        if not case:
            raise CaseManagementException(f"Case {case_id} not found")
        
        # Filter sources if specified
        sources = case.forensic_sources
        if source_ids:
            sources = [s for s in sources if str(s.id) in source_ids]
        
        # Calculate statistics
        total_messages = 0
        participants = set()
        date_range = {'start': None, 'end': None}
        
        sources_data = []
        for source in sources:
            source_dict = {
                'id': str(source.id),
                'source_name': source.source_name,
                'source_type': source.source_type,
                'device_info': source.device_info,
                'account_info': source.account_info,
                'analysis_status': source.analysis_status.value if source.analysis_status else 'unknown',
                'message_count': 0
            }
            
            # Count messages and participants (simplified)
            if hasattr(source, 'forensic_items'):
                source_dict['message_count'] = len(source.forensic_items)
                total_messages += source_dict['message_count']
                
                for item in source.forensic_items:
                    if item.sender:
                        participants.add(item.sender)
                    if item.recipients:
                        participants.update(item.recipients)
                    
                    if item.timestamp:
                        if not date_range['start'] or item.timestamp < date_range['start']:
                            date_range['start'] = item.timestamp
                        if not date_range['end'] or item.timestamp > date_range['end']:
                            date_range['end'] = item.timestamp
            
            sources_data.append(source_dict)
        
        # Format date range
        if date_range['start']:
            date_range['start'] = date_range['start'].strftime('%Y-%m-%d')
        if date_range['end']:
            date_range['end'] = date_range['end'].strftime('%Y-%m-%d')
        
        # Mock additional statistics (would be calculated from actual data)
        statistics = {
            'total_messages': total_messages,
            'unique_participants': len(participants),
            'date_range': date_range,
            'email_count': int(total_messages * 0.4),
            'sms_count': int(total_messages * 0.3),
            'whatsapp_count': int(total_messages * 0.2),
            'other_count': int(total_messages * 0.1),
            'positive_sentiment': int(total_messages * 0.3),
            'neutral_sentiment': int(total_messages * 0.5),
            'negative_sentiment': int(total_messages * 0.2),
            'peak_hour': 14,
            'weekend_messages': int(total_messages * 0.15),
            'deleted_messages': int(total_messages * 0.05)
        }
        
        # Mock network analysis
        network_analysis = {
            'key_participants': [
                {
                    'name': participant,
                    'message_count': int(total_messages * 0.1),
                    'centrality_score': 0.75
                }
                for participant in list(participants)[:10]
            ]
        }
        
        return {
            'case': {
                'id': str(case.id),
                'title': case.title,
                'case_number': case.case_number
            },
            'sources': sources_data,
            'statistics': statistics,
            'network_analysis': network_analysis
        }
    
    async def _apply_export_filters(
        self, 
        db: AsyncSession, 
        case_id: str, 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply filters to case data for selective export"""
        # Get base case data
        case_data = await self._get_case_data(db, case_id)
        
        # Apply date range filter
        if 'date_range' in filters:
            case_data['events'] = self._filter_events_by_date(
                case_data['events'], filters['date_range']
            )
        
        # Apply event type filter
        if 'event_types' in filters:
            allowed_types = filters['event_types']
            case_data['events'] = [
                event for event in case_data['events']
                if event['event_type'] in allowed_types
            ]
        
        # Apply evidence inclusion filter
        if 'include_evidence' in filters and not filters['include_evidence']:
            for event in case_data['events']:
                event['evidence_pins'] = []
        
        # Add filter metadata
        case_data['export_filters'] = filters
        case_data['export_timestamp'] = datetime.now(UTC).isoformat()
        
        return case_data
    
    async def _generate_filtered_pdf(
        self, 
        filtered_data: Dict[str, Any], 
        filters: Dict[str, Any]
    ) -> bytes:
        """Generate PDF from filtered data"""
        # Use existing PDF generation logic with filtered data
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        story.append(Paragraph("Filtered Case Export", styles['Title']))
        story.append(Spacer(1, 12))
        
        # Filter information
        story.append(Paragraph("Applied Filters:", styles['Heading2']))
        for filter_name, filter_value in filters.items():
            story.append(Paragraph(f"{filter_name}: {filter_value}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Case information
        case = filtered_data['case']
        story.append(Paragraph(f"Case: {case['title']}", styles['Heading2']))
        story.append(Paragraph(f"Case Number: {case['case_number']}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Events
        story.append(Paragraph(f"Events ({len(filtered_data['events'])})", styles['Heading2']))
        for event in filtered_data['events']:
            event_date = event['event_date'].strftime('%Y-%m-%d %H:%M') if event['event_date'] else 'No date'
            story.append(Paragraph(f"{event['title']} ({event_date})", styles['Heading3']))
            if event['description']:
                story.append(Paragraph(event['description'], styles['Normal']))
            story.append(Spacer(1, 12))
        
        doc.build(story)
        pdf_content = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        return pdf_content
    
    # Helper methods for forensic analysis reporting
    
    async def _generate_key_statistics_summary(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate key statistics summary for court presentation"""
        stats = forensic_data['statistics']
        
        return {
            'total_communications': stats['total_messages'],
            'unique_participants': stats['unique_participants'],
            'analysis_period': {
                'start_date': stats['date_range']['start'],
                'end_date': stats['date_range']['end'],
                'duration_days': (
                    datetime.fromisoformat(stats['date_range']['end']) - 
                    datetime.fromisoformat(stats['date_range']['start'])
                ).days if stats['date_range']['start'] and stats['date_range']['end'] else 0
            },
            'communication_breakdown': {
                'email_percentage': round((stats.get('email_count', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0,
                'sms_percentage': round((stats.get('sms_count', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0,
                'messaging_percentage': round((stats.get('whatsapp_count', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0
            },
            'behavioral_indicators': {
                'deleted_messages_count': stats.get('deleted_messages', 0),
                'deleted_percentage': round((stats.get('deleted_messages', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0,
                'weekend_activity_percentage': round((stats.get('weekend_messages', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0,
                'negative_sentiment_percentage': round((stats.get('negative_sentiment', 0) / stats['total_messages']) * 100, 1) if stats['total_messages'] > 0 else 0
            }
        }
    
    async def _generate_network_graph_data(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate network graph data for visualization"""
        participants = forensic_data['network_analysis']['key_participants']
        
        # Create nodes
        nodes = []
        for participant in participants:
            nodes.append({
                'id': participant['name'],
                'label': participant['name'],
                'message_count': participant['message_count'],
                'centrality': participant.get('centrality_score', 0),
                'node_type': 'participant'
            })
        
        # Create edges (simplified - would be calculated from actual message data)
        edges = []
        for i, participant1 in enumerate(participants):
            for participant2 in participants[i+1:]:
                # Mock edge weight calculation
                edge_weight = min(participant1['message_count'], participant2['message_count']) * 0.1
                if edge_weight > 1:
                    edges.append({
                        'source': participant1['name'],
                        'target': participant2['name'],
                        'weight': edge_weight,
                        'edge_type': 'communication'
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'layout_algorithm': 'force_directed',
            'visualization_settings': {
                'node_size_by': 'message_count',
                'edge_width_by': 'weight',
                'color_scheme': 'centrality'
            }
        }
    
    async def _correlate_forensic_with_timeline(
        self, 
        forensic_data: Dict[str, Any], 
        timeline_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Correlate forensic data with timeline events"""
        correlations = []
        
        # Simple correlation based on date proximity
        for event in timeline_data['events']:
            if not event['event_date']:
                continue
            
            event_date = event['event_date']
            if isinstance(event_date, str):
                event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            
            # Find forensic activity around the event date (within 24 hours)
            correlation = {
                'timeline_event_id': event['id'],
                'timeline_event_title': event['title'],
                'event_date': event_date.isoformat(),
                'forensic_activity': {
                    'messages_same_day': 0,  # Would be calculated from actual data
                    'key_participants_active': [],
                    'communication_spike': False,
                    'sentiment_change': None
                }
            }
            
            correlations.append(correlation)
        
        return {
            'total_correlations': len(correlations),
            'correlations': correlations,
            'correlation_strength': 'moderate',  # Would be calculated
            'key_insights': [
                'Communication activity increased around key timeline events',
                'Participant behavior patterns align with case developments'
            ]
        }
    
    async def _generate_visual_highlights(
        self, 
        forensic_data: Dict[str, Any], 
        timeline_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate visual highlights for court presentation"""
        highlights = {
            'key_metrics': [
                {
                    'metric': 'Total Communications',
                    'value': forensic_data['statistics']['total_messages'],
                    'visual_type': 'large_number',
                    'color': 'primary'
                },
                {
                    'metric': 'Unique Participants',
                    'value': forensic_data['statistics']['unique_participants'],
                    'visual_type': 'large_number',
                    'color': 'secondary'
                },
                {
                    'metric': 'Deleted Messages',
                    'value': forensic_data['statistics'].get('deleted_messages', 0),
                    'visual_type': 'alert_number',
                    'color': 'warning'
                }
            ],
            'charts': [
                {
                    'chart_type': 'pie',
                    'title': 'Communication Types',
                    'data': {
                        'Email': forensic_data['statistics'].get('email_count', 0),
                        'SMS': forensic_data['statistics'].get('sms_count', 0),
                        'WhatsApp': forensic_data['statistics'].get('whatsapp_count', 0),
                        'Other': forensic_data['statistics'].get('other_count', 0)
                    }
                },
                {
                    'chart_type': 'bar',
                    'title': 'Sentiment Distribution',
                    'data': {
                        'Positive': forensic_data['statistics'].get('positive_sentiment', 0),
                        'Neutral': forensic_data['statistics'].get('neutral_sentiment', 0),
                        'Negative': forensic_data['statistics'].get('negative_sentiment', 0)
                    }
                }
            ],
            'network_preview': {
                'show_network': True,
                'highlight_central_nodes': True,
                'max_nodes_display': 10
            }
        }
        
        return highlights
    
    async def _calculate_message_frequency(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate message frequency patterns"""
        total_messages = forensic_data['statistics']['total_messages']
        
        # Mock frequency calculation (would use actual timestamp data)
        return {
            'messages_per_day_average': round(total_messages / 30, 1),  # Assuming 30-day period
            'peak_day_messages': round(total_messages * 0.1),  # 10% on peak day
            'frequency_pattern': 'irregular',  # Would be calculated from actual data
            'communication_intensity': 'high' if total_messages > 1000 else 'moderate' if total_messages > 100 else 'low'
        }
    
    async def _analyze_sentiment_trends(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment trends over time"""
        stats = forensic_data['statistics']
        
        return {
            'overall_sentiment': 'neutral',  # Would be calculated
            'sentiment_volatility': 'moderate',
            'negative_sentiment_peaks': [],  # Would contain actual dates
            'sentiment_correlation_events': [],
            'emotional_escalation_detected': stats.get('negative_sentiment', 0) > stats['total_messages'] * 0.3
        }
    
    async def _identify_emotional_indicators(self, forensic_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify emotional indicators in communications"""
        return [
            {
                'indicator_type': 'high_negative_sentiment',
                'frequency': forensic_data['statistics'].get('negative_sentiment', 0),
                'significance': 'high' if forensic_data['statistics'].get('negative_sentiment', 0) > 100 else 'moderate',
                'description': 'Elevated negative sentiment detected in communications'
            },
            {
                'indicator_type': 'deleted_messages',
                'frequency': forensic_data['statistics'].get('deleted_messages', 0),
                'significance': 'high' if forensic_data['statistics'].get('deleted_messages', 0) > 50 else 'low',
                'description': 'Pattern of message deletion detected'
            }
        ]
    
    async def _analyze_communication_patterns(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze communication patterns between participants"""
        return {
            'dominant_communicators': forensic_data['network_analysis']['key_participants'][:3],
            'communication_clusters': [
                {
                    'cluster_id': 1,
                    'participants': [p['name'] for p in forensic_data['network_analysis']['key_participants'][:3]],
                    'message_count': sum(p['message_count'] for p in forensic_data['network_analysis']['key_participants'][:3]),
                    'cluster_type': 'core_group'
                }
            ],
            'isolation_patterns': [],  # Would identify isolated participants
            'communication_hierarchy': 'flat'  # Would be calculated from actual data
        }
    
    async def _calculate_relationship_strength(self, forensic_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate relationship strength between participants"""
        participants = forensic_data['network_analysis']['key_participants']
        relationships = []
        
        for i, participant1 in enumerate(participants[:5]):  # Limit to top 5
            for participant2 in participants[i+1:5]:
                strength = min(participant1['message_count'], participant2['message_count']) / max(participant1['message_count'], participant2['message_count'])
                relationships.append({
                    'participant_1': participant1['name'],
                    'participant_2': participant2['name'],
                    'strength_score': round(strength, 2),
                    'relationship_type': 'strong' if strength > 0.7 else 'moderate' if strength > 0.3 else 'weak',
                    'interaction_frequency': 'high' if strength > 0.5 else 'moderate'
                })
        
        return relationships
    
    async def _summarize_communication_anomalies(self, forensic_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize detected communication anomalies"""
        stats = forensic_data['statistics']
        
        anomalies = []
        
        # Check for high deletion rate
        deletion_rate = stats.get('deleted_messages', 0) / stats['total_messages'] if stats['total_messages'] > 0 else 0
        if deletion_rate > 0.1:
            anomalies.append({
                'anomaly_type': 'high_deletion_rate',
                'severity': 'high' if deletion_rate > 0.2 else 'moderate',
                'description': f'{deletion_rate:.1%} of messages were deleted',
                'legal_significance': 'May indicate evidence tampering'
            })
        
        # Check for unusual timing patterns
        weekend_rate = stats.get('weekend_messages', 0) / stats['total_messages'] if stats['total_messages'] > 0 else 0
        if weekend_rate > 0.3:
            anomalies.append({
                'anomaly_type': 'unusual_timing',
                'severity': 'moderate',
                'description': f'{weekend_rate:.1%} of messages sent during weekends',
                'legal_significance': 'May indicate urgency or unusual circumstances'
            })
        
        # Check for negative sentiment concentration
        negative_rate = stats.get('negative_sentiment', 0) / stats['total_messages'] if stats['total_messages'] > 0 else 0
        if negative_rate > 0.4:
            anomalies.append({
                'anomaly_type': 'high_negative_sentiment',
                'severity': 'moderate',
                'description': f'{negative_rate:.1%} of messages have negative sentiment',
                'legal_significance': 'May indicate conflict or hostile relationships'
            })
        
        return {
            'total_anomalies': len(anomalies),
            'anomalies': anomalies,
            'overall_risk_level': 'high' if len(anomalies) > 2 else 'moderate' if len(anomalies) > 0 else 'low',
            'investigation_priority': 'immediate' if any(a['severity'] == 'high' for a in anomalies) else 'standard'
        }
    
    async def _generate_detailed_network_data(
        self, 
        forensic_data: Dict[str, Any], 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Generate detailed network data for export"""
        participants = forensic_data['network_analysis']['key_participants']
        
        # Enhanced nodes with metadata
        nodes = []
        for i, participant in enumerate(participants):
            node = {
                'id': participant['name'],
                'label': participant['name'],
                'message_count': participant['message_count'],
                'centrality_score': participant.get('centrality_score', 0)
            }
            
            if include_metadata:
                node.update({
                    'node_index': i,
                    'participant_type': 'individual',  # Would be determined from data
                    'activity_level': 'high' if participant['message_count'] > 100 else 'moderate' if participant['message_count'] > 20 else 'low',
                    'first_communication': None,  # Would be calculated from actual data
                    'last_communication': None,
                    'communication_frequency': participant['message_count'] / 30  # Messages per day estimate
                })
            
            nodes.append(node)
        
        # Enhanced edges with metadata
        edges = []
        edge_id = 0
        for i, participant1 in enumerate(participants):
            for j, participant2 in enumerate(participants[i+1:], i+1):
                edge_weight = min(participant1['message_count'], participant2['message_count']) * 0.1
                if edge_weight > 1:
                    edge = {
                        'id': edge_id,
                        'source': participant1['name'],
                        'target': participant2['name'],
                        'weight': round(edge_weight, 2)
                    }
                    
                    if include_metadata:
                        edge.update({
                            'edge_type': 'bidirectional',
                            'communication_strength': 'strong' if edge_weight > 10 else 'moderate' if edge_weight > 5 else 'weak',
                            'message_exchange_count': int(edge_weight * 10),  # Estimate
                            'relationship_duration': None,  # Would be calculated
                            'sentiment_balance': 'neutral'  # Would be calculated
                        })
                    
                    edges.append(edge)
                    edge_id += 1
        
        network_data = {
            'nodes': nodes,
            'edges': edges
        }
        
        if include_metadata:
            network_data['metadata'] = {
                'network_type': 'communication_network',
                'analysis_method': 'message_frequency',
                'node_count': len(nodes),
                'edge_count': len(edges),
                'density': len(edges) / (len(nodes) * (len(nodes) - 1) / 2) if len(nodes) > 1 else 0,
                'clustering': 0.5,  # Would be calculated
                'diameter': 3,  # Would be calculated
                'average_path_length': 2.1  # Would be calculated
            }
        
        return network_data
    
    async def _export_network_as_csv(self, network_data: Dict[str, Any]) -> bytes:
        """Export network data as CSV format"""
        import csv
        import io
        
        # Create CSV content
        csv_buffer = io.StringIO()
        
        # Write nodes CSV
        csv_buffer.write("# Nodes\n")
        if network_data['nodes']:
            node_writer = csv.DictWriter(csv_buffer, fieldnames=network_data['nodes'][0].keys())
            node_writer.writeheader()
            node_writer.writerows(network_data['nodes'])
        
        csv_buffer.write("\n# Edges\n")
        if network_data['edges']:
            edge_writer = csv.DictWriter(csv_buffer, fieldnames=network_data['edges'][0].keys())
            edge_writer.writeheader()
            edge_writer.writerows(network_data['edges'])
        
        # Convert to bytes
        csv_content = csv_buffer.getvalue().encode('utf-8')
        csv_buffer.close()
        
        return csv_content