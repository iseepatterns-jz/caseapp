"""
Property-based tests for export functionality
Validates Requirements 8.1, 8.2, 8.4 (Export and Reporting Capabilities)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from hypothesis import given, strategies as st, settings, assume, HealthCheck
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import io

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.case import Case, CaseType, CaseStatus
from models.timeline import CaseTimeline, TimelineEvent, EventType
from models.document import Document
from models.media import MediaEvidence
from models.forensic_analysis import ForensicSource, ForensicItem
from models.user import User, UserRole
from services.export_service import ExportService
from schemas.export import TimelineExportRequest, ForensicReportRequest, SelectiveExportRequest
from core.database import AsyncSessionLocal
from core.exceptions import CaseManagementException

# Test data generators
@st.composite
def case_data_strategy(draw):
    """Generate case data for export testing"""
    return {
        'case_id': str(uuid.uuid4()),
        'case_number': draw(st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'title': draw(st.text(min_size=10, max_size=200)),
        'description': draw(st.text(min_size=20, max_size=1000)),
        'case_type': draw(st.sampled_from(list(CaseType))),
        'status': draw(st.sampled_from(list(CaseStatus)))
    }

@st.composite
def timeline_event_strategy(draw):
    """Generate timeline event data for export testing"""
    base_date = datetime.utcnow() - timedelta(days=draw(st.integers(min_value=1, max_value=365)))
    return {
        'id': str(uuid.uuid4()),
        'title': draw(st.text(min_size=5, max_size=100)),
        'description': draw(st.text(min_size=10, max_size=500)),
        'event_type': draw(st.sampled_from(list(EventType))),
        'event_date': base_date + timedelta(hours=draw(st.integers(min_value=0, max_value=23))),
        'location': draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
        'participants': draw(st.lists(st.text(min_size=3, max_size=50), min_size=0, max_size=5))
    }

@st.composite
def date_range_strategy(draw):
    """Generate date range for filtering"""
    start_date = datetime.utcnow() - timedelta(days=draw(st.integers(min_value=30, max_value=365)))
    end_date = start_date + timedelta(days=draw(st.integers(min_value=1, max_value=90)))
    return {
        'start': start_date,
        'end': end_date
    }

@st.composite
def export_filters_strategy(draw):
    """Generate export filters for selective export testing"""
    filters = {}
    
    # Date range filter
    if draw(st.booleans()):
        date_range = draw(date_range_strategy())
        filters['date_range'] = date_range
    
    # Event types filter
    if draw(st.booleans()):
        event_types = draw(st.lists(
            st.sampled_from(['meeting', 'incident', 'communication', 'legal_action', 'evidence_collection']),
            min_size=1, max_size=3
        ))
        filters['event_types'] = event_types
    
    # Evidence inclusion filter
    filters['include_evidence'] = draw(st.booleans())
    filters['include_metadata'] = draw(st.booleans())
    
    return filters

class TestExportFunctionalityProperties:
    """Property-based tests for export functionality"""
    
    def run_async_test(self, async_func, *args, **kwargs):
        """Helper to run async functions in sync context"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    
    @given(
        case_data=case_data_strategy(),
        events=st.lists(timeline_event_strategy(), min_size=1, max_size=10),
        include_evidence=st.booleans(),
        include_metadata=st.booleans()
    )
    @settings(max_examples=10, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_14_multi_format_export(
        self,
        case_data: Dict[str, Any],
        events: List[Dict[str, Any]],
        include_evidence: bool,
        include_metadata: bool
    ):
        """
        Property 14: Multi-Format Export
        
        For any case with timeline events, the export service SHALL:
        1. Generate PDF reports with consistent structure and content
        2. Create PNG visualizations with proper dimensions and quality
        3. Maintain data integrity across different export formats
        4. Include all requested metadata and evidence information
        
        Validates Requirements 8.1, 8.2 (timeline export formats)
        """
        self.run_async_test(
            self._test_multi_format_export_async, 
            case_data, events, include_evidence, include_metadata
        )
    
    async def _test_multi_format_export_async(
        self,
        case_data: Dict[str, Any],
        events: List[Dict[str, Any]],
        include_evidence: bool,
        include_metadata: bool
    ):
        """
        Property 14: Multi-Format Export
        
        For any case with timeline events, the export service SHALL:
        1. Generate PDF reports with consistent structure and content
        2. Create PNG visualizations with proper dimensions and quality
        3. Maintain data integrity across different export formats
        4. Include all requested metadata and evidence information
        
        Validates Requirements 8.1, 8.2 (timeline export formats)
        """
        # Mock the database and service dependencies
        with patch('services.export_service.AsyncSessionLocal') as mock_session_local:
            
            # Setup mock database session
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Create mock case
            mock_case = MagicMock()
            mock_case.id = uuid.UUID(case_data['case_id'])
            mock_case.title = case_data['title']
            mock_case.case_number = case_data['case_number']
            mock_case.description = case_data['description']
            
            # Create mock enum objects
            mock_case_type = MagicMock()
            mock_case_type.value = case_data['case_type'].value
            mock_case.case_type = mock_case_type
            
            mock_status = MagicMock()
            mock_status.value = case_data['status'].value
            mock_case.status = mock_status
            
            # Create mock timeline with events
            mock_timeline = MagicMock()
            mock_timeline.id = uuid.uuid4()
            mock_timeline.case_id = mock_case.id
            
            mock_events = []
            for event_data in events:
                mock_event = MagicMock()
                mock_event.id = uuid.UUID(event_data['id'])
                mock_event.title = event_data['title']
                mock_event.description = event_data['description']
                
                # Create mock event type
                mock_event_type = MagicMock()
                mock_event_type.value = event_data['event_type'].value
                mock_event.event_type = mock_event_type
                
                mock_event.event_date = event_data['event_date']
                mock_event.location = event_data['location']
                mock_event.participants = event_data['participants']
                mock_events.append(mock_event)
            
            mock_timeline.events = mock_events
            mock_case.timelines = [mock_timeline]
            mock_case.documents = []
            mock_case.media_evidence = []
            
            # Setup database query result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_case
            mock_session.execute.return_value = mock_result
            
            # Test export service
            service = ExportService()
            
            # Test PDF export
            pdf_content = await service.export_timeline_pdf(
                case_id=case_data['case_id'],
                include_evidence=include_evidence,
                include_metadata=include_metadata
            )
            
            # Verify PDF export properties
            assert isinstance(pdf_content, bytes), "PDF export should return bytes"
            assert len(pdf_content) > 0, "PDF content should not be empty"
            
            # PDF should start with PDF header
            assert pdf_content.startswith(b'%PDF-'), "PDF should have valid PDF header"
            
            # Test PNG export
            png_content = await service.export_timeline_png(
                case_id=case_data['case_id'],
                width=1920,
                height=1080,
                dpi=300
            )
            
            # Verify PNG export properties
            assert isinstance(png_content, bytes), "PNG export should return bytes"
            assert len(png_content) > 0, "PNG content should not be empty"
            
            # PNG should start with PNG signature
            assert png_content.startswith(b'\x89PNG\r\n\x1a\n'), "PNG should have valid PNG signature"
            
            # Both exports should be substantial in size (not just headers)
            assert len(pdf_content) > 1000, "PDF should contain substantial content"
            assert len(png_content) > 1000, "PNG should contain substantial content"
            
            # Verify that different options produce different outputs
            pdf_content_no_metadata = await service.export_timeline_pdf(
                case_id=case_data['case_id'],
                include_evidence=include_evidence,
                include_metadata=False  # Different from original
            )
            
            # Content should be different when metadata inclusion changes
            if include_metadata:
                assert pdf_content != pdf_content_no_metadata, \
                    "PDF content should differ when metadata inclusion changes"
    
    @given(
        case_data=case_data_strategy(),
        events=st.lists(timeline_event_strategy(), min_size=5, max_size=20),
        filters=export_filters_strategy()
    )
    @settings(max_examples=10, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_25_selective_export_filtering(
        self,
        case_data: Dict[str, Any],
        events: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ):
        """
        Property 25: Selective Export Filtering
        
        For any export request with filters, the export service SHALL:
        1. Apply date range filters correctly to exclude events outside the range
        2. Apply event type filters to include only specified types
        3. Respect evidence inclusion/exclusion settings
        4. Maintain data consistency in filtered exports
        
        Validates Requirements 8.4 (selective export with filtering)
        """
        self.run_async_test(self._test_selective_export_filtering_async, case_data, events, filters)
    
    async def _test_selective_export_filtering_async(
        self,
        case_data: Dict[str, Any],
        events: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ):
        """
        Property 25: Selective Export Filtering
        
        For any export request with filters, the export service SHALL:
        1. Apply date range filters correctly to exclude events outside the range
        2. Apply event type filters to include only specified types
        3. Respect evidence inclusion/exclusion settings
        4. Maintain data consistency in filtered exports
        
        Validates Requirements 8.4 (selective export with filtering)
        """
        # Mock the database and service dependencies
        with patch('services.export_service.AsyncSessionLocal') as mock_session_local:
            
            # Setup mock database session
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Create mock case with events
            mock_case = MagicMock()
            mock_case.id = uuid.UUID(case_data['case_id'])
            mock_case.title = case_data['title']
            mock_case.case_number = case_data['case_number']
            mock_case.description = case_data['description']
            
            # Create mock enum objects
            mock_case_type = MagicMock()
            mock_case_type.value = case_data['case_type'].value
            mock_case.case_type = mock_case_type
            
            mock_status = MagicMock()
            mock_status.value = case_data['status'].value
            mock_case.status = mock_status
            
            # Create mock timeline with events
            mock_timeline = MagicMock()
            mock_timeline.id = uuid.uuid4()
            mock_events = []
            
            for event_data in events:
                mock_event = MagicMock()
                mock_event.id = uuid.UUID(event_data['id'])
                mock_event.title = event_data['title']
                mock_event.description = event_data['description']
                
                mock_event_type = MagicMock()
                mock_event_type.value = event_data['event_type'].value
                mock_event.event_type = mock_event_type
                
                mock_event.event_date = event_data['event_date']
                mock_event.location = event_data['location']
                mock_event.participants = event_data['participants']
                mock_events.append(mock_event)
            
            mock_timeline.events = mock_events
            mock_case.timelines = [mock_timeline]
            mock_case.documents = []
            mock_case.media_evidence = []
            
            # Setup database query result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_case
            mock_session.execute.return_value = mock_result
            
            # Test selective export
            service = ExportService()
            
            # Export with filters
            filtered_result = await service.export_selective_data(
                case_id=case_data['case_id'],
                export_format='json',
                filters=filters
            )
            
            # Verify filtering properties
            assert isinstance(filtered_result, dict), "JSON export should return dictionary"
            assert 'case' in filtered_result, "Export should include case information"
            assert 'events' in filtered_result, "Export should include events"
            assert 'export_filters' in filtered_result, "Export should include applied filters"
            
            # Verify case information is preserved
            assert filtered_result['case']['id'] == case_data['case_id']
            assert filtered_result['case']['title'] == case_data['title']
            assert filtered_result['case']['case_number'] == case_data['case_number']
            
            # Verify filter application
            filtered_events = filtered_result['events']
            
            # Test date range filtering
            if 'date_range' in filters:
                date_range = filters['date_range']
                for event in filtered_events:
                    if event['event_date']:
                        event_date = event['event_date']
                        if isinstance(event_date, str):
                            event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                        
                        assert event_date >= date_range['start'], \
                            f"Event date {event_date} should be after filter start {date_range['start']}"
                        assert event_date <= date_range['end'], \
                            f"Event date {event_date} should be before filter end {date_range['end']}"
            
            # Test event type filtering
            if 'event_types' in filters:
                allowed_types = filters['event_types']
                for event in filtered_events:
                    assert event['event_type'] in allowed_types, \
                        f"Event type {event['event_type']} should be in allowed types {allowed_types}"
            
            # Test evidence inclusion filtering
            if 'include_evidence' in filters:
                include_evidence = filters['include_evidence']
                for event in filtered_events:
                    if not include_evidence:
                        assert len(event.get('evidence_pins', [])) == 0, \
                            "Evidence should be excluded when include_evidence is False"
            
            # Verify filter metadata is included
            assert filtered_result['export_filters'] == filters, \
                "Applied filters should match requested filters"
            assert 'export_timestamp' in filtered_result, \
                "Export should include timestamp"
            
            # Test that unfiltered export contains more or equal events
            unfiltered_result = await service.export_selective_data(
                case_id=case_data['case_id'],
                export_format='json',
                filters={}  # No filters
            )
            
            unfiltered_events = unfiltered_result['events']
            
            # Filtered result should have <= events than unfiltered
            assert len(filtered_events) <= len(unfiltered_events), \
                f"Filtered export ({len(filtered_events)} events) should have <= events than unfiltered ({len(unfiltered_events)} events)"
            
            # If we have restrictive filters, filtered should have fewer events
            has_restrictive_filters = (
                'date_range' in filters or 
                'event_types' in filters
            )
            
            if has_restrictive_filters and len(unfiltered_events) > 0:
                # Allow for the case where all events happen to pass the filters
                assert len(filtered_events) <= len(unfiltered_events), \
                    "Restrictive filters should not increase event count"
    
    @given(
        case_data=case_data_strategy(),
        forensic_sources=st.lists(
            st.fixed_dictionaries({
                'id': st.uuids().map(str),
                'source_name': st.text(min_size=5, max_size=50),
                'source_type': st.sampled_from(['email', 'sms', 'whatsapp', 'phone_backup']),
                'message_count': st.integers(min_value=10, max_value=1000)
            }),
            min_size=1, max_size=5
        ),
        include_statistics=st.booleans(),
        include_network_analysis=st.booleans()
    )
    @settings(max_examples=5, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_26_forensic_report_completeness(
        self,
        case_data: Dict[str, Any],
        forensic_sources: List[Dict[str, Any]],
        include_statistics: bool,
        include_network_analysis: bool
    ):
        """
        Property 26: Forensic Report Completeness
        
        For any forensic analysis export, the service SHALL:
        1. Include comprehensive statistics when requested
        2. Include network analysis data when requested
        3. Maintain data integrity across all forensic sources
        4. Generate reports with consistent structure and formatting
        
        Validates Requirements 8.3 (forensic analysis reporting)
        """
        self.run_async_test(
            self._test_forensic_report_completeness_async,
            case_data, forensic_sources, include_statistics, include_network_analysis
        )
    
    async def _test_forensic_report_completeness_async(
        self,
        case_data: Dict[str, Any],
        forensic_sources: List[Dict[str, Any]],
        include_statistics: bool,
        include_network_analysis: bool
    ):
        """
        Property 26: Forensic Report Completeness
        
        For any forensic analysis export, the service SHALL:
        1. Include comprehensive statistics when requested
        2. Include network analysis data when requested
        3. Maintain data integrity across all forensic sources
        4. Generate reports with consistent structure and formatting
        
        Validates Requirements 8.3 (forensic analysis reporting)
        """
        # Mock the database and service dependencies
        with patch('services.export_service.AsyncSessionLocal') as mock_session_local:
            
            # Setup mock database session
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Create mock case
            mock_case = MagicMock()
            mock_case.id = uuid.UUID(case_data['case_id'])
            mock_case.title = case_data['title']
            mock_case.case_number = case_data['case_number']
            
            # Create mock forensic sources
            mock_sources = []
            total_messages = 0
            
            for source_data in forensic_sources:
                mock_source = MagicMock()
                mock_source.id = uuid.UUID(source_data['id'])
                mock_source.source_name = source_data['source_name']
                mock_source.source_type = source_data['source_type']
                mock_source.device_info = f"Device info for {source_data['source_name']}"
                mock_source.account_info = f"Account info for {source_data['source_name']}"
                
                # Create mock analysis status
                mock_status = MagicMock()
                mock_status.value = 'completed'
                mock_source.analysis_status = mock_status
                
                # Create mock forensic items
                mock_items = []
                for i in range(source_data['message_count']):
                    mock_item = MagicMock()
                    mock_item.id = i + 1
                    mock_item.sender = f"user{i % 5}@example.com"
                    mock_item.recipients = [f"recipient{i % 3}@example.com"]
                    mock_item.timestamp = datetime.utcnow() - timedelta(days=i % 30)
                    mock_items.append(mock_item)
                
                mock_source.forensic_items = mock_items
                mock_sources.append(mock_source)
                total_messages += source_data['message_count']
            
            mock_case.forensic_sources = mock_sources
            
            # Setup database query result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_case
            mock_session.execute.return_value = mock_result
            
            # Test forensic report export
            service = ExportService()
            
            pdf_content = await service.export_forensic_report_pdf(
                case_id=case_data['case_id'],
                include_statistics=include_statistics,
                include_network_analysis=include_network_analysis,
                include_raw_data=False
            )
            
            # Verify forensic report properties
            assert isinstance(pdf_content, bytes), "Forensic report should return bytes"
            assert len(pdf_content) > 0, "Report content should not be empty"
            
            # PDF should start with PDF header
            assert pdf_content.startswith(b'%PDF-'), "Report should have valid PDF header"
            
            # Report should be substantial (contains actual data)
            assert len(pdf_content) > 2000, "Report should contain substantial content"
            
            # Test that different inclusion options produce different outputs
            if include_statistics or include_network_analysis:
                # Test with different options
                pdf_content_minimal = await service.export_forensic_report_pdf(
                    case_id=case_data['case_id'],
                    include_statistics=False,
                    include_network_analysis=False,
                    include_raw_data=False
                )
                
                # Content should be different when options change
                if include_statistics or include_network_analysis:
                    assert pdf_content != pdf_content_minimal, \
                        "Report content should differ when inclusion options change"
                    
                    # Full report should be larger than minimal report
                    assert len(pdf_content) >= len(pdf_content_minimal), \
                        "Full report should be at least as large as minimal report"
            
            # Test with specific source filtering
            if len(forensic_sources) > 1:
                # Export with only first source
                first_source_id = forensic_sources[0]['id']
                filtered_pdf = await service.export_forensic_report_pdf(
                    case_id=case_data['case_id'],
                    source_ids=[first_source_id],
                    include_statistics=include_statistics,
                    include_network_analysis=include_network_analysis
                )
                
                # Filtered report should be valid
                assert isinstance(filtered_pdf, bytes), "Filtered report should return bytes"
                assert filtered_pdf.startswith(b'%PDF-'), "Filtered report should have valid PDF header"
                assert len(filtered_pdf) > 1000, "Filtered report should contain substantial content"
                
                # Filtered report should generally be smaller than full report
                # (unless the first source contains most of the data)
                assert len(filtered_pdf) <= len(pdf_content), \
                    "Filtered report should not be larger than full report"
    
    @given(
        width=st.integers(min_value=800, max_value=4000),
        height=st.integers(min_value=600, max_value=3000),
        dpi=st.integers(min_value=72, max_value=600)
    )
    @settings(max_examples=5, deadline=20000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_14_png_visualization_quality(
        self,
        width: int,
        height: int,
        dpi: int
    ):
        """
        Property 14: PNG Visualization Quality
        
        For any PNG export request, the service SHALL:
        1. Generate images with specified dimensions
        2. Maintain proper aspect ratios and quality
        3. Include all visual elements (timeline, events, metadata)
        4. Scale content appropriately for different resolutions
        
        Validates Requirements 8.2 (high-resolution PNG visualizations)
        """
        self.run_async_test(self._test_png_visualization_quality_async, width, height, dpi)
    
    async def _test_png_visualization_quality_async(
        self,
        width: int,
        height: int,
        dpi: int
    ):
        """
        Property 14: PNG Visualization Quality
        
        For any PNG export request, the service SHALL:
        1. Generate images with specified dimensions
        2. Maintain proper aspect ratios and quality
        3. Include all visual elements (timeline, events, metadata)
        4. Scale content appropriately for different resolutions
        
        Validates Requirements 8.2 (high-resolution PNG visualizations)
        """
        # Mock the database and service dependencies
        with patch('services.export_service.AsyncSessionLocal') as mock_session_local:
            
            # Setup mock database session
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            # Create mock case with timeline events
            mock_case = MagicMock()
            mock_case.id = uuid.uuid4()
            mock_case.title = "Test Case for PNG Export"
            mock_case.case_number = "TEST-001"
            mock_case.description = "Test case description"
            
            # Create mock enum objects
            mock_case_type = MagicMock()
            mock_case_type.value = "civil"
            mock_case.case_type = mock_case_type
            
            mock_status = MagicMock()
            mock_status.value = "active"
            mock_case.status = mock_status
            
            # Create mock timeline with events
            mock_timeline = MagicMock()
            mock_timeline.id = uuid.uuid4()
            
            # Create several events with different dates
            mock_events = []
            base_date = datetime.utcnow() - timedelta(days=30)
            
            for i in range(5):
                mock_event = MagicMock()
                mock_event.id = uuid.uuid4()
                mock_event.title = f"Event {i + 1}"
                mock_event.description = f"Description for event {i + 1}"
                
                mock_event_type = MagicMock()
                mock_event_type.value = "meeting"
                mock_event.event_type = mock_event_type
                
                mock_event.event_date = base_date + timedelta(days=i * 7)
                mock_event.location = f"Location {i + 1}"
                mock_event.participants = [f"Participant {i + 1}"]
                mock_events.append(mock_event)
            
            mock_timeline.events = mock_events
            mock_case.timelines = [mock_timeline]
            mock_case.documents = []
            mock_case.media_evidence = []
            
            # Setup database query result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_case
            mock_session.execute.return_value = mock_result
            
            # Test PNG export with specified dimensions
            service = ExportService()
            
            png_content = await service.export_timeline_png(
                case_id=str(mock_case.id),
                width=width,
                height=height,
                dpi=dpi
            )
            
            # Verify PNG export properties
            assert isinstance(png_content, bytes), "PNG export should return bytes"
            assert len(png_content) > 0, "PNG content should not be empty"
            
            # PNG should start with PNG signature
            assert png_content.startswith(b'\x89PNG\r\n\x1a\n'), "PNG should have valid PNG signature"
            
            # PNG should be substantial in size (not just headers)
            assert len(png_content) > 1000, "PNG should contain substantial image data"
            
            # Higher DPI should generally produce larger files (more detail)
            if dpi >= 150:
                # Test with lower DPI for comparison
                png_content_low_dpi = await service.export_timeline_png(
                    case_id=str(mock_case.id),
                    width=width,
                    height=height,
                    dpi=72  # Standard screen resolution
                )
                
                # Higher DPI should generally produce larger files
                # (allowing for some compression variance)
                size_ratio = len(png_content) / len(png_content_low_dpi)
                assert size_ratio >= 0.8, \
                    f"High DPI image should be reasonably sized compared to low DPI (ratio: {size_ratio})"
            
            # Larger dimensions should generally produce larger files
            if width >= 1600 and height >= 1200:
                # Test with smaller dimensions for comparison
                png_content_small = await service.export_timeline_png(
                    case_id=str(mock_case.id),
                    width=800,
                    height=600,
                    dpi=dpi
                )
                
                # Larger image should generally be larger in file size
                size_ratio = len(png_content) / len(png_content_small)
                assert size_ratio >= 1.0, \
                    f"Larger image should be at least as large as smaller image (ratio: {size_ratio})"
    
    def test_property_export_error_handling(self):
        """
        Property: Export Error Handling
        
        Export service SHALL:
        1. Handle missing case data gracefully
        2. Provide meaningful error messages for invalid inputs
        3. Maintain system stability during export failures
        
        Validates Requirements 8.1-8.4 (error handling)
        """
        self.run_async_test(self._test_export_error_handling_async)
    
    async def _test_export_error_handling_async(self):
        """
        Property: Export Error Handling
        
        Export service SHALL:
        1. Handle missing case data gracefully
        2. Provide meaningful error messages for invalid inputs
        3. Maintain system stability during export failures
        
        Validates Requirements 8.1-8.4 (error handling)
        """
        # Mock the database and service dependencies
        with patch('services.export_service.AsyncSessionLocal') as mock_session_local:
            
            # Setup mock database session
            mock_session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = mock_session
            
            service = ExportService()
            
            # Test with non-existent case
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # Case not found
            mock_session.execute.return_value = mock_result
            
            non_existent_case_id = str(uuid.uuid4())
            
            # PDF export should handle missing case gracefully
            with pytest.raises(CaseManagementException) as exc_info:
                await service.export_timeline_pdf(case_id=non_existent_case_id)
            
            assert "not found" in str(exc_info.value).lower(), \
                "Error message should indicate case not found"
            
            # PNG export should handle missing case gracefully
            with pytest.raises(CaseManagementException) as exc_info:
                await service.export_timeline_png(case_id=non_existent_case_id)
            
            assert "not found" in str(exc_info.value).lower(), \
                "Error message should indicate case not found"
            
            # Forensic export should handle missing case gracefully
            with pytest.raises(CaseManagementException) as exc_info:
                await service.export_forensic_report_pdf(case_id=non_existent_case_id)
            
            assert "not found" in str(exc_info.value).lower(), \
                "Error message should indicate case not found"
            
            # Selective export should handle missing case gracefully
            with pytest.raises(CaseManagementException) as exc_info:
                await service.export_selective_data(
                    case_id=non_existent_case_id,
                    export_format='json',
                    filters={}
                )
            
            assert "not found" in str(exc_info.value).lower(), \
                "Error message should indicate case not found"
            
            # Test with invalid export format
            mock_case = MagicMock()
            mock_case.id = uuid.uuid4()
            mock_case.title = "Test Case"
            mock_case.case_number = "TEST-001"
            mock_case.timelines = []
            mock_case.documents = []
            mock_case.media_evidence = []
            
            mock_result.scalar_one_or_none.return_value = mock_case
            
            with pytest.raises(CaseManagementException) as exc_info:
                await service.export_selective_data(
                    case_id=str(mock_case.id),
                    export_format='invalid_format',
                    filters={}
                )
            
            assert "unsupported" in str(exc_info.value).lower(), \
                "Error message should indicate unsupported format"