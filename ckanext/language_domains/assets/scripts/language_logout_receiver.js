window.addEventListener('message', function(_event){

  const trusted_domains = TRUSTED_LANG_DOMAINS || [];

  if( ! Array.prototype.includes.call(trusted_domains, _event.origin) ){
    return;
  }

  if( typeof _event.data.logout_receiver_ready != 'undefined' ){
    _event.source.postMessage({'logout_receiver_ready': true}, _event.origin);
    return;
  }

  if( ! _event.data.session_user || ! _event.data.session_token || ! _event.data.target_domain || ! _event.data.target_language ){
    return;
  }

  let tokenFieldName = $('meta[name="csrf_field_name"]').attr('content');
  let tokenValue = $('meta[name="' + tokenFieldName + '"]').attr('content');
  _event.data[tokenFieldName] = tokenValue;

  $.ajax({
    'url': '/user/language_domain_logout',
    'type': 'POST',
    'dataType': 'JSON',
    'data': _event.data,
    'complete': function(_data){
      if( _data.responseJSON ){  // we have response JSON
        if( _data.responseJSON.success ){  // successful format guess
          _event.source.postMessage({'logout_successful': true}, _event.origin);
        }else{  // validation error
          _event.source.postMessage({'logout_successful': false}, _event.origin);
        }
      }else{  // fully flopped ajax request
        _event.source.postMessage({'logout_successful': false}, _event.origin);
      }
    }
  });

});