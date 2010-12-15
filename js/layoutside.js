(function () {
    var config = {
        column_count: 24,
        column_width: 30,
        gutter_width: 10,
        totalColWidth: 40 // column_width + gutter_width
    };   
    
    /* main */
    var Layoutside = function () {
        var self = this;
        lg('loaded...');

        // menu bar
        $('#save-layout').click(saveLayout);

        this.Toolbar.init();
        this.Container.init();
        this.Editor.init();
        
        $(document).keydown(function (e) {
            if(e.keyCode == $.ui.keyCode.ESCAPE) {
                var cs = self.Container.currentSection;
                // não remover container quando selecionado
                if(cs[0] != self.Container.ui[0]) {
                    cs.remove();
                    self.Container.currentSection = self.Container.ui;
                    self.Container.addLast();
                }
            }
        });
    }, parent = Layoutside.prototype;
   
   
    function saveLayout() {
        var layout = {
            'config': config,
            'sections': []
        };
        
        function iter(context) {
            $('> .section', context).each(function (k, v) {
                var $elm = $(v), childs = $elm.children('.section');    
                
                var section = {
                    'name': 'section name ' + k,
                    'tagname': v.tagName, 
                    'body': $elm.find('.section-content').html(),
                    'html_id': v.id,
                    'css_class': v.className,
                    'width': parent.Container.getSectionWidth($elm),
                    'parent': (typeof context == 'object' ? context.id : null),
                    'order': k,
                };
                
                layout.sections.push(section);
                
                if(childs.length) {
                    iter(v);
                }
            });    
        }
        
        iter('#container');
        // console.log(layout);
        // carregar layout
        /*
        foreach section
            if section have parent
                continue
            addSection(section)    
        foreach section
            addSection(section)
        */
        /*
        var i = 0, l = layout.sections.length;
        
        for(; i < l; i++) {
            if(layout.sections[i].parent) {
                continue;
            }
            
            lg('append "' + layout.sections[i].name + '"');
            parent.Container.addSection(layout.sections[i]);
            
            delete layout.sections[i];
        }
        
        for(i = 0; i < l; i++) {
            if (layout.sections[i] === undefined) 
                continue;

            lg('append child: "' + layout.sections[i].name + '"');
            parent.Container.addSection(layout.sections[i]);
        }
        */ 
        
        $.ajax({ type: "POST",
            url: 'ajax.php',
            data: $.param(layout),
            success: function(result){
                lg('Layout saved');
            }
        });
        
        return false;          
    }
    
    Layoutside.prototype.Container = {
        editMode: '', 
        ui: $('#container'),
        grid: $('#containerGrid'), 
        currentSection: null,
        isResizingSection: false, 
        
        init: function () {
            var self = this;
            this.setEditMode('select');
            this.currentSection = this.ui;
            
            this.ui.add(this.grid).click(function (e) {
                self.setCurrentSection(self.ui); 
                self.setMeasures();
            });
        }, 

        setEditMode: function (mode) {
            if(this.editMode == mode)
                return null;

            this.editMode = mode;
            var isSortable = this.ui.hasClass('ui-sortable'), self = this; 
            
            parent.Toolbar.ui.find('a.icon-select, a.icon-sort')
                .removeClass('icon-active');

            switch(mode) {
                case 'sort':
                    $('a.icon-sort').addClass('icon-active');

                    if(!isSortable) {
                        this.ui.sortable({
                            items: '> div[class^=span]',
                            scroll: false, 
                            opacity: 0.6, 
                            cursor: 'move', 
                            grid: [config.totalColWidth, 10],
                            start: function (e, ui) {   
                                var ch = ui.helper.height();
                                ui.placeholder.height(ch);
                            }, 
                            stop: function () {
                                self.addLast();
                            }
                        });
                    } else 
                        this.ui.sortable('enable');

                    break;
                case 'select':
                default:
                    if(isSortable)
                        this.ui.sortable('disable');
                    $('a.icon-select').addClass('icon-active');
            }
        },
        
        setCurrentSection: function (node) {
            var curClass = 'current-section', $n = $(node);
            
            this.ui.find('.' + curClass).removeClass(curClass);
            if($n.hasClass('section'))
                $n.addClass(curClass);
            this.currentSection = $n; 
        }, 

        getSectionWidth: function (elm) {
            return parseInt(elm[0].className.split(' ')[0].split('-')[1]);
        },
 
        addLast: function (context) {
            var hasContext = typeof context !== 'undefined', 
                sections = $('> .section',  hasContext ? context : this.ui), 
                sum = 0, columnCount = config.column_count, i, f;

            if(hasContext) 
                columnCount = this.getSectionWidth(context);

            sections.filter('.last').removeClass('last');
            sections.filter('.clear').removeClass('clear');
            
            for(i = 0, f = sections.length; i < f; i = i + 1) {
                var curSection = $(sections[i]), 
                    prevColumnCount = this.getSectionWidth(curSection),
                    nextSection = curSection.next('.section');

                sum += prevColumnCount;

                if(sum > columnCount) {
                    curSection.toggleClass('clear');
                    sum = prevColumnCount;
                } else if(sum == columnCount) {
                    curSection.toggleClass('last');
                  
                    if(nextSection.length)
                        nextSection.toggleClass('clear');
                    sum = 0;
                } 
                
                // tem sub sections?
                if(curSection.find('.section').length)
                    this.addLast(curSection);
            }
        },

        setMeasures: function (w, h) {
            var container = parent.Container, 
                w = w ? w : container.ui.width(),
                h = h ? h : container.ui.height();
            
            parent.Toolbar.widthInput.val(w);
            parent.Toolbar.heightInput.val(h);
        },
        
        currentSectionId: 1,
        
        addSection: function (old_section) {
            var id = old_section ? old_section.html_id : this.currentSectionId++;
            var content = old_section ? old_section.body : '';
            var sec_width = old_section ? old_section.width : 3;
            
            var section = $('<div id="section-' + id + '" class="span-' + 
                sec_width + ' section"><div class="section-content"></div></div>');
            
            section.find('.section-content').html(content);
            
            var self = this, sectionDialog = parent.Dialogs.initSection(section),
                hoverClass = 'hover-section', nclicks = 0, lastClass = 1;
            
            
            section.click(function (e) {
                e.stopPropagation();
                nclicks = nclicks + 1;

                if (nclicks < 2) { 
                    self.setCurrentSection(section.get(0));
                    self.setMeasures(section.width(), section.height());
                    window.setTimeout(function () {
                        nclicks = 0;
                    }, 500);
                } else { // handle dblclick
                    sectionDialog.dialog('open');
                    nclicks = 0;
                }
            }); 

            section.mouseover(function (e) {  
                if(self.isResizingSection)
                    return false;
                    
                e.stopPropagation();
                section.addClass(hoverClass);
            }).mouseout(function (e) {  
                section.removeClass(hoverClass);
            });

            var lastResizedParent = null;
            
            section.resizable({
               // minHeight: 24,
                maxWidth: 950, 
                autoHide: true,
                zIndex: 100, 
                grid: [config.totalColWidth],
                handles: 'e', 
                // containment: 'parent', 
                
                start: function (e, ui) { },
                stop: function () { }, 
                
                resize: function (e, ui) { 
                    var elm = ui.helper, sectionWidth = elm.width(), curClass = '', 
                        nc = Math.round(sectionWidth / config.totalColWidth);

                    parent.Toolbar.heightInput.val(ui.size.height);

                    if(lastClass == nc) 
                        return false;

                    var childs = elm.find('> .section');

                    // preservar largura min/max quando ouver 'filhos'                    
                    if(childs.length) {
                        var largSection = self.getSectionWidth(elm), largMaiorFilho = 0;
                        
                        childs.each(function (k, v) {
                            var $c = $(v), cw = self.getSectionWidth($c);

                            lgm('max child w', sectionWidth);
                            $c.resizable("option", "maxWidth", sectionWidth);   
                                
                            if(cw > largMaiorFilho)
                                largMaiorFilho = cw;
                        });                 

                        section.resizable("option", "minWidth", 
                            largMaiorFilho * config.totalColWidth);
                    }

                    
                    lastClass = nc;
                    curClass = elm[0].className;
                    elm[0].className = curClass.replace(/^span-\d+/, 'span-' + nc);
                    self.addLast();
                    parent.Toolbar.widthInput.val(sectionWidth);
                }
            });
/*
            var target = this.currentSection[0] == self.ui[0] ? 
                self.ui : this.currentSection.find('> .section-content');
            target.append(section);
            */
            
            // definir largumar maxima da section quando filha
            if(this.currentSection[0] != self.ui[0]) {
                lgm('maxwidth', self.getSectionWidth(this.currentSection) * config.totalColWidth);
                section.resizable("option", "maxWidth", 
                    self.getSectionWidth(this.currentSection) * config.totalColWidth);         
            }           
            
            if(old_section && old_section.parent !== null)
                $('#' + old_section.parent).append(section);
            else 
                this.currentSection.append(section);
                
            this.addLast();
        },
        
        toggleGrid: function () {
            $('#containerGrid').toggleClass('togglegrid');
        },

        updateGridHeight: function () {
            $('#containerGrid').height(parent.Container.ui.height() + 40);
        }
    };
    
    Layoutside.prototype.Layout = {
        open: function () { 
            lg('open layout'); 

            for(var i = 0 ; i < 7; i++)
                parent.Container.addSection();  
                
            this.buildGrid();
            parent.Container.setMeasures();
        },

        save: function () {lg('saving');},        
        saveAs: function () {lg('save as');},        
        // getCode: function () {lg('give me the code');},
        download: function () {},
        buildGrid: function () {
            var ui = $('#containerGrid'), i = 0;
            var clm = {};
            
            for(; i < config.column_count; i++){
                clm = $(document.createElement('div'));
                clm.css({ width: config.column_width , 
                    marginRight: config.gutter_width
                })
                ui.append(clm);
            }
                
            ui.find('div:last').css('marginRight', 0);
        }
        
    };
    
    Layoutside.prototype.Toolbar = {
        ui: $('#toolbar'),
        widthInput: $('#section-w').val(0), 
        heightInput: $('#section-h').val(0), 

        init: function () {
            var c = parent.Container, self = this;

            $('a.icon').click(function (e) { e.preventDefault(); } );

            $('a.icon-select').bind('click', function () { c.setEditMode('select'); });
            $('a.icon-sort').bind('click', function () { c.setEditMode('sort'); });

            $('a.icon-section').bind('click', function () { c.addSection(); });
            $('a.icon-toggle-grid').bind('click', function () { c.toggleGrid(); });

            this.heightInput.keyup(function () {
                var h = self.heightInput.val(), s = parent.Container.currentSection;

                if(!isNaN(h) && !s.hasClass('container')) {
                    h = parseInt(h);
                    if(h < 24) // min-height
                        return false;
                    s.height(h);
                }
            });
        }
    };
    
    Layoutside.prototype.Dialogs = {
        sectionUi: $(".sectionDialog"), 
        
        initSection: function (section) {
            var nd = this.sectionUi.clone();

            nd.dialog({
                resizable: false, autoOpen: false, width: 300, height: 225, 
                open: function () {
                    lg('section dialog open');
                }
		    });

            $('.space-slider', nd).slider( {
	            min: 1, max: config.column_count,
                start: function () { }
            });

		    return nd;
        }
    };
    
    Layoutside.prototype.Editor = {
        editor: null,
        dialogUi: null, 
        stylePath: 'js/codemirror/css/',
        
        init: function () {
            this.setupDialog();
//            $(this.editor).appendTo('#editorAres');
            
            $('#openEditor').click(function (e) {
                $('#editor').dialog('open');
                e.preventDefault();
            });
        },
        startEditor: function () {
            if(this.editor === null)
                this.editor = $('#sourceEditor');
            /*
                this.editor = CodeMirror.fromTextArea('sourceEditor', {
                    parserfile: ["parsexml.js", 
                        "parsecss.js", 
                        "tokenizejavascript.js", 
                        "parsejavascript.js", 
                        "parsehtmlmixed.js"],
                    stylesheet: [this.stylePath + "xmlcolors.css", 
                        this.stylePath + "jscolors.css", 
                        this.stylePath + "csscolors.css"],
                    path: 'js/codemirror/js/'
                });
            */
        },
        setupDialog: function () {
            var target = null, self = this;
            this.dialogUi = $('#editor');
            
            this.dialogUi.dialog({
                resizable: true, autoOpen: false, width: '65%', height: 400,
                buttons: {
                    'Update': function () {
                        if(target == null)
                            return false;
                        var c = self.editor.val(); // getCode
                        target.find('> .section-content').html(c);        
                        parent.Container.updateGridHeight();
                    },
                    'Close': function () {
                        self.dialogUi.dialog('close');
                    }
                }, 
                open: function () {
                    self.startEditor();

                    var sections = parent.Container.ui.find('> .section');
                    var o = null;
                    
                    $('#section-list').html('');
                    
                    sections.each(function (i, s) {
                        o = document.createElement('option');
                        o.innerHTML = 'Section ' + (i + 1);
                        $(o).data('domNode', s);
                        $('#section-list').append(o);                
                    });
                    
                    target = $($('#section-list option:first').data('domNode'));
                    self.editor.html(target.find('.section-content').html()); // setCode           
                }
            }); 

            $('#section-list').change(function () {
                target = $($(this).find('option')
                    .eq($(this).attr('selectedIndex')).data('domNode'));
                self.editor.val(target.find('.section-content').html()); // setCode
            });
        }
    };
    
    window.Layoutside = Layoutside;

    var lg = function (f) { 
        if(!console) return false;
        console.log(f);
    }, lgm = function (m, v) {
        lg(m + ': ' + v);
    };
    
})();

